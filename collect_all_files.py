import pathlib

def merge_contents(output_filename="all_files.txt"):
    # 👇 既然脚本在项目根目录了，当前目录就是项目根目录！
    project_root = pathlib.Path(__file__).absolute().parent
    print(f"📦 当前项目根目录: {project_root}")
    
    # 确保输出文件依然生成在 .local 文件夹内（眼不见心不烦）
    output_path = project_root / '.local' / output_filename
    
    # 统计合并的文件数量
    count = 0
    
    with output_path.open('w', encoding='utf-8') as outfile:
        ignored_dirs = {'.git', '.local'}

        # 从项目根目录开始遍历所有文件
        for file_path in project_root.rglob('*'):
            
            # 跳过仓库元数据和私密变量目录，避免把密钥合并到调试输出里。
            if any(part in ignored_dirs for part in file_path.parts):
                continue

            # 忽略特定的二进制/图片文件后缀
            ignored_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.zip', '.tar', '.gz', '.rar', '.7z', '.vault'}
            if file_path.suffix.lower() in ignored_extensions:
                continue

            # 过滤条件：必须是文件、不是脚本本身
            if file_path.is_file() and file_path.name != 'collect_all_files.py' and file_path.name != output_filename:
                
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # 写入文件分隔符和相对路径
                    outfile.write(f"\n{'='*50}\n")
                    outfile.write(f"FILE: {file_path.relative_to(project_root)}\n")
                    outfile.write(f"{'='*50}\n\n")
                    
                    outfile.write(content)
                    outfile.write("\n")
                    
                    print(f"已处理: {file_path.relative_to(project_root)}")
                    count += 1
                    
                except Exception as e:
                    print(f"无法读取 {file_path}: {e}")

    print(f"\n✅ 完成！共合并了 {count} 个文件，已保存至 {output_path}")

if __name__ == "__main__":
    merge_contents()
