> 归档位置：`docs/rob2_reference/rob2_questions.md`（Standard ROB2）
> 机器可读题库：`src/rob2/rob2_questions.yaml`
> Domain 2 采用唯一 planner ID：assignment 使用 `q2a_*`，adherence 使用 `q2b_*`；`rob2_id` 保留原始 `q2_*` 编号。

这是一个基于 Cochrane RoB 2（随机对照试验偏倚风险评估工具 2.0）标准的结构化表格。

1.  **信号问题表 (Signaling Questions)**：包含每个领域的具体评估问题。
2.  **领域总体评估选项 (Overall Domain Risk)**：包含每个领域的最终风险评级选项。

### 1. 偏倚风险评估信号问题表

**图例说明：**
*   **Y**: Yes (是)
*   **PY**: Probably Yes (可能是)
*   **PN**: Probably No (可能否)
*   **N**: No (否)
*   **NI**: No Information (无信息)
*   **NA**: Not Applicable (不适用)

| 领域 (Domain) | 编号 (ID) | 信号问题 (Signaling Question) | 选项 (Options) |
| :--- | :--- | :--- | :--- |
| **Risk of bias arising from the randomization process**<br>(随机化过程引起的偏倚风险) | q1_1 | Was the allocation sequence random? | Y, PY, PN, N, NI |
| | q1_2 | Was the allocation sequence concealed until participants were enrolled and assigned to interventions? | Y, PY, PN, N, NI |
| | q1_3 | Did baseline differences between intervention groups suggest a problem with the randomization process? | Y, PY, PN, N, NI |
| **Risk of bias due to deviations from the intended interventions (effect of assignment)**<br>(偏离既定干预引起的偏倚风险 - 分配效应) | q2_1 | Were participants aware of their assigned intervention during the trial? | Y, PY, PN, N, NI |
| | q2_2 | Were carers and people delivering the interventions aware of participants' assigned intervention during the trial? | Y, PY, PN, N, NI |
| | q2_3 | If Y/PY/NI to 2.1 or 2.2: Were there deviations from the intended intervention that arose because of the trial context? | NA, Y, PY, PN, N, NI |
| | q2_4 | If Y/PY to 2.3: Were these deviations likely to have affected the outcome? | NA, Y, PY, PN, N, NI |
| | q2_5 | If Y/PY/NI to 2.4: Were these deviations from intended intervention balanced between groups? | NA, Y, PY, PN, N, NI |
| | q2_6 | Was an appropriate analysis used to estimate the effect of assignment to intervention? | Y, PY, PN, N, NI |
| | q2_7 | If N/PN/NI to 2.6: Was there potential for a substantial impact (on the result) of the failure to analyse participants in the group to which they were randomized? | NA, Y, PY, PN, N, NI |
| **Risk of bias due to deviations from the intended interventions (effect of adherence)**<br>(偏离既定干预引起的偏倚风险 - 依从性效应) | q2_1 | Were participants aware of their assigned intervention during the trial? | Y, PY, PN, N, NI |
| | q2_2 | Were carers and people delivering the interventions aware of participants' assigned intervention during the trial? | Y, PY, PN, N, NI |
| | q2_3 | If Y/PY/NI to 2.1 or 2.2: Were important non-protocol interventions balanced across intervention groups? | NA, Y, PY, PN, N, NI |
| | q2_4 | Were there failures in implementing the intervention that could have affected the outcome? | NA, Y, PY, PN, N, NI |
| | q2_5 | Was there non-adherence to the assigned intervention regimen that could have affected participants’ outcomes? | NA, Y, PY, PN, N, NI |
| | q2_6 | If N/PN/NI to 2.3, or Y/PY/NI to 2.4 or 2.5: Was an appropriate analysis used to estimate the effect of adhering to the intervention? | NA, Y, PY, PN, N, NI |
| **Risk of bias due to missing outcome data**<br>(缺失结局数据引起的偏倚风险) | q3_1 | Were data for this outcome available for all, or nearly all, participants randomized? | Y, PY, PN, N, NI |
| | q3_2 | If N/PN/NI to 3.1: Is there evidence that the result was not biased by missing outcome data? | NA, Y, PY, PN, N |
| | q3_3 | If N/PN to 3.2: Could missingness in the outcome depend on its true value? | NA, Y, PY, PN, N, NI |
| | q3_4 | If Y/PY/NI to 3.3: Is it likely that missingness in the outcome depended on its true value? | NA, Y, PY, PN, N, NI |
| **Risk of bias in measurement of the outcome**<br>(结局测量中的偏倚风险) | q4_1 | Was the method of measuring the outcome inappropriate? | Y, PY, PN, N, NI |
| | q4_2 | Could measurement or ascertainment of the outcome have differed between intervention groups? | Y, PY, PN, N, NI |
| | q4_3 | If N/PN/NI to 4.1 and 4.2: Were outcome assessors aware of the intervention received by study participants? | NA, Y, PY, PN, N, NI |
| | q4_4 | If Y/PY/NI to 4.3: Could assessment of the outcome have been influenced by knowledge of intervention received? | NA, Y, PY, PN, N, NI |
| | q4_5 | If Y/PY/NI to 4.4: Is it likely that assessment of the outcome was influenced by knowledge of intervention received? | NA, Y, PY, PN, N, NI |
| **Risk of bias in selection of the reported result**<br>(结果报告选择中的偏倚风险) | q5_1 | Were the data that produced this result analysed in accordance with a pre-specified analysis plan that was finalized before unblinded outcome data were available for analysis? | Y, PY, PN, N, NI |
| | q5_2 | Was the result selected from multiple eligible outcome measurements (e.g. scales, definitions, time points) within the outcome domain? | Y, PY, PN, N, NI |
| | q5_3 | Was the result selected from multiple eligible analyses of the data? | Y, PY, PN, N, NI |

---

### 2. 决策树
---

## **Domain 1：随机化过程**

**输入：1.1 / 1.2 / 1.3 → 输出：域内判定**

| 条件组合                                                  | 判定                                  |
| ----------------------------------------------------- | ----------------------------------- |
| 1.2 = **N/PN**                                        | **High**                            |
| 1.2 = **NI** 且 1.3 = **Y/PY**                         | **High**                            |
| 1.2 = **Y/PY** 且 1.3 = **N/PN 或 NI**（1.1 = Y/PY 或 NI） | **Low**                             |
| 1.2 = **Y/PY** 且 1.3 = **Y/PY**                       | **Some concerns** *(严重不平衡可上调 High)* |
| 1.2 = **NI** 且 1.3 = **N/PN 或 NI**                    | **Some concerns**                   |
| 1.1 = 1.2 = 1.3 = **NI**                              | **Some concerns**                   |

---

## **Domain 2：偏离既定干预（effect of assignment）**

**输入：2.6 / 2.7 → 输出**

| 条件组合                                    | 判定                |
| --------------------------------------- | ----------------- |
| 2.6 = **Y/PY**                          | **Low**           |
| 2.6 = **N/PN/NI** 且 2.7 = **N/PN**      | **Some concerns** |
| 2.6 = **N/PN/NI** 且 2.7 = **Y/PY 或 NI** | **High**          |

---

## **Domain 3：缺失结局数据**

**输入：3.1–3.4 → 输出**

| 条件组合                                                            | 判定                |
| --------------------------------------------------------------- | ----------------- |
| 3.1 = **Y/PY**                                                  | **Low**           |
| 3.1 ≠ Y/PY 且 3.2 = **Y/PY**                                     | **Low**           |
| 3.1 ≠ Y/PY 且 3.2 ≠ Y/PY 且 3.3 = **N/PN**                        | **Low**           |
| 3.1 ≠ Y/PY 且 3.2 ≠ Y/PY 且 3.3 = **Y/PY/NI** 且 3.4 = **N/PN**    | **Some concerns** |
| 3.1 ≠ Y/PY 且 3.2 ≠ Y/PY 且 3.3 = **Y/PY/NI** 且 3.4 = **Y/PY/NI** | **High**          |

---

## **Domain 4：结局测量**

**输入：4.1–4.5 → 输出（必须包含 4.2）**

| 条件组合                                                                                    | 判定                |
| --------------------------------------------------------------------------------------- | ----------------- |
| 4.1 = **Y/PY**                                                                          | **High**          |
| 4.2 = **Y/PY**                                                                          | **High**          |
| 4.1 ≠ Y/PY 且 4.2 = **N/PN** 且 4.3 = **N/PN**                                            | **Low**           |
| 4.1 ≠ Y/PY 且 4.2 = **N/PN** 且 4.3 = **Y/PY/NI** 且 4.4 = **N/PN**                        | **Low**           |
| 4.1 ≠ Y/PY 且 4.2 = **N/PN** 且 4.3 = **Y/PY/NI** 且 4.4 = **Y/PY/NI** 且 4.5 = **N/PN**    | **Some concerns** |
| 4.1 ≠ Y/PY 且 4.2 = **N/PN** 且 4.3 = **Y/PY/NI** 且 4.4 = **Y/PY/NI** 且 4.5 = **Y/PY/NI** | **High**          |
| 4.2 = **NI**（且未触发 High）                                                                 | **Some concerns** |

---

## **Domain 5：选择性报告**

**输入：5.1 / 5.2 / 5.3 → 输出**

| 条件组合                                                | 判定                |
| --------------------------------------------------- | ----------------- |
| 5.2 = **Y/PY**                                      | **High**          |
| 5.3 = **Y/PY**                                      | **High**          |
| 5.1 = **Y/PY** 且 5.2 = **N/PN** 且 5.3 = **N/PN**    | **Low**           |
| 5.1 = **N/PN/NI** 且 5.2 = **N/PN** 且 5.3 = **N/PN** | **Some concerns** |
| 5.2 = **NI** 或 5.3 = **NI**（且未触发 High）              | **Some concerns** |
