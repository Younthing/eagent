import hashlib
import os
from collections.abc import Mapping

from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

if not (os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")):
    raise EnvironmentError(
        "未检测到 LANGSMITH_API_KEY（或 LANGCHAIN_API_KEY），请在 .env 中配置后重试。"
    )

client = Client()

PROJECT_NAME = os.getenv("LANGSMITH_PROJECT", "literature-agent")
DATASET_NAME = "Literature_Cleaned_Dataset"


def extract_user_and_output(run):
    """
    专门针对你截图中包含 SystemMessage 和 HumanMessage 的嵌套 JSON 进行精准提取
    """
    inputs = run.inputs
    outputs = run.outputs
    if not inputs or not outputs:
        return None, None

    user_text = None
    ai_text = None

    # --- 1. 提取输入：跳过系统提示词，只拿用户输入 ---
    if "messages" in inputs:
        messages = inputs["messages"]
        if isinstance(messages, list) and len(messages) > 0:
            # 解决 LangChain 的双层嵌套 [[{...}, {...}]]
            inner_messages = messages[0] if isinstance(messages[0], list) else messages

            for msg in inner_messages:
                if not isinstance(msg, Mapping):
                    continue
                kwargs = msg.get("kwargs", {})
                if not isinstance(kwargs, Mapping):
                    continue
                msg_type = kwargs.get("type", "")
                msg_id = msg.get("id", [])

                # 精准匹配：只抓取 HumanMessage (用户输入)
                if "HumanMessage" in msg_id or msg_type == "human":
                    user_text = kwargs.get("content", "")
                    break  # 找到用户输入就跳出

    # --- 2. 提取输出：直接拿大模型生成的纯文本 ---
    if "generations" in outputs:
        generations = outputs["generations"]
        if isinstance(generations, list) and len(generations) > 0:
            inner_gens = (
                generations[0] if isinstance(generations[0], list) else generations
            )
            if isinstance(inner_gens, list) and len(inner_gens) > 0:
                # 提取纯文本 JSON 结果
                first_gen = inner_gens[0]
                if isinstance(first_gen, Mapping):
                    ai_text = first_gen.get("text", "")

    if user_text and ai_text:
        return {"user_input": user_text}, {"ai_output": ai_text}
    return None, None


def build_fingerprint(inputs: dict[str, str], outputs: dict[str, str]) -> str:
    """使用输入输出内容做哈希，避免重复导入内容相同的数据。"""
    payload = f"{inputs.get('user_input', '').strip()}\n\n{outputs.get('ai_output', '').strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_dedup_index(dataset_id) -> tuple[set[str], set[str], int]:
    """加载已有样本，构建 run_id 与内容哈希的去重索引。"""
    existing_run_ids: set[str] = set()
    existing_fingerprints: set[str] = set()
    existing_count = 0

    for example in client.list_examples(dataset_id=dataset_id):
        existing_count += 1
        source_run_id = getattr(example, "source_run_id", None)
        if source_run_id:
            existing_run_ids.add(str(source_run_id))

        example_inputs = example.inputs or {}
        example_outputs = example.outputs or {}
        user_text = example_inputs.get("user_input")
        ai_text = example_outputs.get("ai_output")

        if isinstance(user_text, str) and isinstance(ai_text, str) and user_text and ai_text:
            existing_fingerprints.add(
                build_fingerprint(
                    {"user_input": user_text},
                    {"ai_output": ai_text},
                )
            )

    return existing_run_ids, existing_fingerprints, existing_count


def main():
    # 2. 创建干净的数据集
    if not client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.create_dataset(dataset_name=DATASET_NAME)
        print(f"✅ 创建新数据集: {DATASET_NAME}")
    else:
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        print(f"ℹ️ 数据集 {DATASET_NAME} 已存在，将追加数据")

    existing_run_ids, existing_fingerprints, existing_count = build_dedup_index(
        dataset.id
    )
    print(
        f"ℹ️ 已加载去重索引：现有样本 {existing_count} 条，source_run_id {len(existing_run_ids)} 个，内容指纹 {len(existing_fingerprints)} 个。"
    )

    # 3. 使用你网页端调试好的过滤器获取 Runs
    print(f"⏳ 正在拉取项目 '{PROJECT_NAME}' 的成功 LLM 调用...")
    runs = client.list_runs(
        project_name=PROJECT_NAME,
        filter='and(eq(run_type, "llm"), eq(status, "success"))',
    )

    # 4. 提取并写入数据集
    success_count = 0
    skipped_count = 0
    duplicated_count = 0
    failed_count = 0
    for run in runs:
        try:
            parsed_input, parsed_output = extract_user_and_output(run)
            if not (parsed_input and parsed_output):
                skipped_count += 1
                print(f"  [-] 格式不匹配，跳过 (Run ID: {run.id})")
                continue

            run_id = str(run.id)
            fingerprint = build_fingerprint(parsed_input, parsed_output)
            if run_id in existing_run_ids or fingerprint in existing_fingerprints:
                duplicated_count += 1
                print(f"  [=] 已存在，跳过重复 (Run ID: {run.id})")
                continue

            client.create_example(
                inputs=parsed_input,
                outputs=parsed_output,
                dataset_id=dataset.id,
                source_run_id=run.id,
            )
            existing_run_ids.add(run_id)
            existing_fingerprints.add(fingerprint)
            success_count += 1
            print(f"  [+] 成功清洗并添加 1 条数据 (Run ID: {run.id})")
        except Exception as exc:
            failed_count += 1
            print(f"  [!] 写入失败，已跳过 (Run ID: {run.id}, Error: {exc})")

    print(
        "\n🎉 搞定！"
        f" 新增 {success_count} 条，重复跳过 {duplicated_count} 条，"
        f" 格式跳过 {skipped_count} 条，失败跳过 {failed_count} 条。"
    )


if __name__ == "__main__":
    main()
