import os
import pathlib

def merge_contents(output_filename="all_files.txt", include_local=True):
    """
    合并项目内所有文件内容。
    
    :param output_filename: 输出的文件名
    :param include_local: 是否收集 .local 文件夹（即使它是软链接）。True 为收集，False 为跳过。
    """
    # 获取脚本所在的项目根目录
    project_root = pathlib.Path(__file__).absolute().parent
    print(f"📦 当前项目根目录: {project_root}")
    
    # 确保输出文件生成在 .local 文件夹内
    output_path = project_root / '.local' / output_filename
    
    # 确保 .local 目录存在（防止因为是全新环境而报错）
    if not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
    count = 0
    
    # 👇 根据你的参数，动态决定要不要忽略 .local
    ignored_dirs = {'.git'}
    if not include_local:
        ignored_dirs.add('.local')
        print("🛑 模式: [跳过] .local 文件夹。")
    else:
        print("✅ 模式: [收集] .local 文件夹（包含软链接内容）。")

    # 忽略特定的二进制/图片文件后缀
    ignored_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.zip', '.tar', '.gz', '.rar', '.7z', '.vault'}

    with output_path.open('w', encoding='utf-8') as outfile:
        # 核心逻辑：使用 os.walk 并强制开启 followlinks=True 以穿透软链接
        for root, dirs, files in os.walk(project_root, followlinks=True):
            
            # 原地修改 dirs 列表，过滤掉 ignored_dirs 里的文件夹
            # 这样 os.walk 就不会进入被忽略的文件夹
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            for file in files:
                file_path = pathlib.Path(root) / file
                
                # 过滤条件 1: 跳过脚本本身
                if file == 'collect_all_files.py' or file == pathlib.Path(__file__).name:
                    continue
                    
                # 过滤条件 2: 绝对不能读取输出文件本身，防止无限套娃死循环
                if file == output_filename:
                    continue
                    
                # 过滤条件 3: 忽略特定后缀
                if file_path.suffix.lower() in ignored_extensions:
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # 获取相对于项目根目录的路径，日志看起来更清晰
                    rel_path = os.path.relpath(file_path, project_root)
                    
                    # 写入文件分隔符和相对路径
                    outfile.write(f"\n{'='*50}\n")
                    outfile.write(f"FILE: {rel_path}\n")
                    outfile.write(f"{'='*50}\n\n")
                    
                    outfile.write(content)
                    outfile.write("\n")
                    
                    print(f"已处理: {rel_path}")
                    count += 1
                    
                except Exception as e:
                    print(f"无法读取 {file_path}: {e}")

    print(f"\n🎉 完成！共合并了 {count} 个文件，已保存至 {output_path}")

if __name__ == "__main__":
    # 👇 在这里控制开关！
    # include_local=True  -> 会钻进 .local 软链接去收集里面的代码
    # include_local=False -> 彻底无视 .local 里面的内容（但输出文件依然会存在那）
    merge_contents(output_filename="all_files.txt", include_local=True)