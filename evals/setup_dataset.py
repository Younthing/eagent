from langsmith import Client

client = Client()

dataset_name = "Literature Agent Test Set"

# 示例数据：包含输入文本和期望的关键结论
examples = [
    {
        "inputs": {
            "doc_structure": {
                "abstract": "摘要：本文提出了Transformer架构，通过自注意力机制...",
                "methods": "结论：该模型在机器翻译任务上得分为 28.4 BLEU。",
            }
        },
        "outputs": {"expected_facts": "Transformer; 自注意力; BLEU 28.4"},
    },
    {
        "inputs": {
            "doc_structure": {
                "abstract": "摘要：我们研究了光合作用在低光照下的效率...",
                "results": "实验显示在弱光条件下效率提高 12%。",
            }
        },
        "outputs": {"expected_facts": "光合作用; 低光照; 效率"},
    },
]


def create_dataset():
    if client.has_dataset(dataset_name=dataset_name):
        print(f"数据集 '{dataset_name}' 已存在。")
        return

    dataset = client.create_dataset(dataset_name=dataset_name)
    client.create_examples(
        inputs=[e["inputs"] for e in examples],
        outputs=[e["outputs"] for e in examples],
        dataset_id=dataset.id,
    )
    print(f"数据集 '{dataset_name}' 创建成功。")


if __name__ == "__main__":
    create_dataset()
