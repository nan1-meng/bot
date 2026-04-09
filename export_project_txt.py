import os

# ----------------------------
# 修改这里：项目路径
project_root = r"F:\Pyproject\chatgpt\tradingbot_reworked_integrated_full\tradingbot_reworked_integrated_full"

# 修改这里：输出 txt 文件路径（桌面）
output_dir  = r"C:\Users\19728\Desktop\full_project_source.txt"
# ----------------------------

# 我把他分成了4份读熟所有的模块最新的代码和逻辑，不要出错，了解之后给我完整的代码结构和对应的功能逻辑，下面是第一份然后等我发完4份之后你就开始
# 创建输出文件夹，如果不存在
os.makedirs(output_dir, exist_ok=True)

# 分成几份
num_splits = 4

# 收集项目里所有 Python 文件
py_files = []
for root, dirs, files in os.walk(project_root):
    for file in files:
        if file.endswith(".py"):
            py_files.append(os.path.join(root, file))

# 计算每份文件数量
total_files = len(py_files)
split_size = total_files // num_splits
remainder = total_files % num_splits

start = 0
for i in range(num_splits):
    end = start + split_size + (1 if i < remainder else 0)  # 前几份多一个文件
    split_files = py_files[start:end]

    # 输出 txt 文件路径
    output_file = os.path.join(output_dir, f"project_part_{i+1}.txt")

    # 写入 txt
    with open(output_file, "w", encoding="utf-8") as out:
        for file_path in split_files:
            rel_path = os.path.relpath(file_path, project_root)
            out.write(f"\n=== 文件: {rel_path} ===\n")
            with open(file_path, "r", encoding="utf-8") as f:
                out.write(f.read() + "\n")

    print(f"生成完成：{output_file}（包含 {len(split_files)} 个文件）")
    start = end

print("全部三份打包完成！")