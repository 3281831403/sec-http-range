下载接口支持区间请求之后，越界区间被当成整文件返回，多区间还拼错了顺序：后缀区间把结束位置当成起点，取到的是前段；起止端点按开区间处理，最后一个字节被漏掉；起点等于大小时判为可满足，返回空内容而不是不可满足；终点超过大小不钳制，读取越界；负起点不拒绝，被当成从头开始；区间数量不设上限，超量请求被接受；重叠区间不合并，重复返回相同字节；多区间按区间长度排序返回，顺序与请求不一致；单位不识别时默认按字节处理，错误单位被接受；零长度资源被判为可满足。byterange/parse.py 是核心，tests/test_parse.py 15个红。要修的是：按上面的顺序把 10 个缺陷逐个修掉。

## 运行方式

在仓库根目录执行：

    python -m pytest tests -q

初始状态必须恰好是 15 failed，并且 15 个失败全部为 NotImplementedError；不能出现 collection、import 或 syntax error。实现 src/byterange/parse.py 后应当变为 15 passed。

只调试一个用例：

    python -m pytest tests/test_parse.py -q -k suffix
    python -m pytest "tests/test_parse.py::test_defect_01_suffix_range_uses_tail_bytes" -q

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 安全 |
| 子方向 | 漏洞检测与攻防 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 文件结构

    sec-http-range/
    ├── README.md
    ├── pyproject.toml
    ├── src/
    │   └── byterange/
    │       ├── __init__.py
    │       └── parse.py
    └── tests/
        └── test_parse.py

## src 布局说明

本仓库采用 src 布局：实现包位于 src/byterange/，而不是仓库根目录下的 byterange/。pyproject.toml 中的 [tool.pytest.ini_options] 设置 pythonpath = ["src"]，pytest 启动时会把 src 加入导入路径，因此运行 python -m pytest tests -q 不需要先执行 pip install，也不会从仓库根误导入同名模块。项目本身只声明元数据，dependencies 为空，不使用任何第三方运行期依赖。

src/byterange/parse.py 是唯一实现文件，恰好包含 8 个待实现函数。src/byterange/__init__.py 只负责导出这些函数，不包含业务逻辑。tests/test_parse.py 恰好包含 15 个用例：前 10 个逐个对应题面中的缺陷，后 5 个覆盖单一闭区间、后缀取到末尾、越界钳制、多区间顺序和两批独立解析。

## 数据结构

区间统一表示为 {"start": int, "end": int}，两个端点都包含在区间内，因此长度为 end - start + 1。不可满足的区间用 end < start 表示；clamp 对起点大于等于资源大小的请求返回 {"start": size, "end": size - 1}。size 为 0 时该标记自然成为 {"start": 0, "end": -1}，调用方不得用它切片。

## 10 条边角约定

1. 单位白名单：parse_unit 只接受 bytes，大小写不敏感，也接受 BYTES=0-1 这种完整头部的前缀形式；返回值统一为小写 bytes。其他单位必须抛出 ValueError，不能默认按字节处理。
2. 闭区间：first-last 的 first 和 last 都是有效字节位置，不按半开区间解释。2-6 在大小为 10 的资源上得到 start 为 2、end 为 6，共 5 个字节，不能漏掉最后一个字节。
3. 起点等于大小：start 等于 size 时没有可读字节，必须判为不可满足，不能返回空内容却声称成功。clamp 用 end 小于 start 的标记表达这一点。
4. 终点越界：last 大于等于 size 时把它钳制到 size - 1，不能直接按原终点读取。例如大小为 10 时 5-50 变成 5-9。
5. 负起点：-5-10 这类负起点不是合法的起点区间，必须抛出 ValueError；不能把负号吃掉后当成从 0 开始。合法的后缀区间只有 -N 这种整体形式。
6. 区间数量上限：MAX_RANGES 固定为 16。逗号分隔的区间数超过 16 时，在解析、合并之前就抛出 ValueError，不能先合并再放行。
7. 重叠与相邻合并：重叠或首尾相接的闭区间必须合并，避免重复返回相同字节。合并后保留最早出现的位置；10-19、0-4、2-12、20-21 合并为单个 0-21。
8. 多区间顺序：返回顺序必须是请求中的出现顺序，不能按区间长度、起点或终点重新排序。sort_specs 只在显式提供 order 字段时按该字段稳定排序，否则保持输入顺序。
9. 零长度资源：size 为 0 时任何区间都不可满足，satisfiable 必须返回 False，parse_set 返回空列表；不能因为区间语法合法就判为可满足。
10. 单位与语义校验顺序：先校验单位，再按逗号计数，然后逐个解析并钳制，最后才合并。非法单位、空成员、缺少端点、非数字和负起点都属于 ValueError；不可满足与语法错误是两类结果，不能混为一谈。

## 批量接口附加约定

range_batch 接收 requests 列表，每项包含 id、header、size，可选 if_range；policy 可包含 max_ranges、merge 和 etag。每个请求独立解析，一个请求失败不影响同一批中的其他请求，也不在不同批次之间共享状态。

条件头组合：请求带有 if_range 且它不等于 policy 中的 etag 时，忽略 Range 并返回整个资源，结果形状为 {"ok": True, "status": 200, "ranges": [], "ignored": True}；验证器匹配时才应用区间。

错误响应分类：语法错误、单位不支持、区间数超限返回 400 和 error 为 invalid_range；size 为 0 或没有任何可满足区间返回 416 和 error 为 unsatisfiable；成功时返回 206 和 ranges。有效上限取 policy 的 max_ranges 与 MAX_RANGES 的较小值，merge 默认 True。

## 测试清单

前 10 个用例与题面缺陷一一对应：

1. test_defect_01_suffix_range_uses_tail_bytes
2. test_defect_02_inclusive_end_keeps_last_byte
3. test_defect_03_start_at_size_is_unsatisfiable
4. test_defect_04_end_beyond_size_is_clamped
5. test_defect_05_negative_start_rejected
6. test_defect_06_too_many_ranges_rejected
7. test_defect_07_overlapping_ranges_merged
8. test_defect_08_multi_range_keeps_request_order
9. test_defect_09_unknown_unit_rejected
10. test_defect_10_zero_length_is_unsatisfiable

后 5 个用例覆盖正常路径和独立性：

11. test_single_closed_range_parses
12. test_suffix_range_reaches_end_byte
13. test_out_of_bounds_range_is_clamped
14. test_multi_range_preserves_request_order
15. test_two_batches_independent

## 约束

1. tests 不可修改：不得增删用例、不得改断言、不得跳过、不得加 xfail；只修改 src/byterange/parse.py 来完成修复。
2. 8 个函数的签名和 docstring 是验收契约，不要改签名，也不要改变 __init__.py 的导出用途。
3. 保持 src 布局和 pyproject.toml 中的 pythonpath 配置；不要把实现包挪到仓库根，也不要依赖 pip install。
4. 初始的 15 个失败必须全部来自 NotImplementedError，不能靠其他异常或收集失败来制造红。
5. 只允许 Python 标准库和 pytest；不联网、不读取真实文件内容、不使用随机数。