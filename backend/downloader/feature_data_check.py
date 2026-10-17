import os
import shutil
import re
from config import config

def delete_targets(root_dir):
    """
    遍历目录并删除符合条件的子目录和文件
    :param root_dir: 要遍历的根目录
    """
    # 用于匹配 "xxx-日期.csv" 格式的正则表达式
    # 日期部分支持 年-月-日 格式
    file_pattern = re.compile(r'^.*\d{4}-\d{2}-\d{2}\.csv$')
    
    # 先收集要删除的目标（避免边遍历边删除导致的路径问题）
    to_delete_dirs = []
    to_delete_files = []
    
    # 遍历目录
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # 检查子目录是否包含"1h"
        for dirname in dirnames:
            dir_fullpath = os.path.join(dirpath, dirname)
            if "1h" == dirname:
                to_delete_dirs.append(dir_fullpath)
        
        # 检查文件是否以"xxx-日期.csv"结尾
        for filename in filenames:
            if file_pattern.match(filename):
                file_fullpath = os.path.join(dirpath, filename)
                to_delete_files.append(file_fullpath)
    
    # 删除符合条件的文件
    for file_path in to_delete_files:
        try:
            os.remove(file_path)
            print(f"已删除文件: {file_path}")
        except Exception as e:
            print(f"删除文件失败 {file_path}: {e}")
    
    # 删除符合条件的目录（包含所有子内容）
    for dir_path in to_delete_dirs:
        try:
            shutil.rmtree(dir_path)
            print(f"已删除目录: {dir_path}")
        except Exception as e:
            print(f"删除目录失败 {dir_path}: {e}")

if __name__ == "__main__":
    # 替换为你要遍历的目录路径
    target_directory = config.BACKTEST_SAMPLE_ORIGIN_DIR+'/monthly'
    
    # 验证目录是否存在
    if not os.path.isdir(target_directory):
        print(f"错误: 目录 {target_directory} 不存在")
    else:
        print(f"开始处理目录: {target_directory}")
        delete_targets(target_directory)
        print("处理完成")