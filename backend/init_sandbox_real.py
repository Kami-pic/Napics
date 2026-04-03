import os
import shutil
import time

# 挂载点，可以指向真实的 NAS
NAS_REAL_ROOT = r"\\DS218play\share\视频"
SANDBOX_REAL_DIR = os.path.join(os.path.dirname(__file__), "sandbox_real")

def create_mirror(src_root, dst_root):
    if not os.path.exists(src_root):
        print(f"❌ 错误: 无法找到真实 NAS 路径 {src_root}。请确保网络驱动器已连接。")
        return

    print(f"🚀 开始 1:1 零字节克隆，源路径: {src_root} ...")
    start_time = time.time()
    
    # 每次克隆前清空上次的第二沙盒
    if os.path.exists(dst_root):
        shutil.rmtree(dst_root)
    os.makedirs(dst_root, exist_ok=True)

    file_count = 0
    folder_count = 0

    # 为了避免死循环和卡在回收站，忽略系统隐藏夹
    ignore_dirs = {".recycle", "@eaDir", "#recycle", "$RECYCLE.BIN", "System Volume Information"}

    try:
        for root, dirs, files in os.walk(src_root):
            # 过滤不需要深挖的系统专属文件夹
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            
            # 计算对应的目标文件夹路径
            rel_path = os.path.relpath(root, src_root)
            if rel_path == ".":
                target_dir = dst_root
            else:
                target_dir = os.path.join(dst_root, rel_path)
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
                folder_count += 1
            
            # 建空壳文件
            for f in files:
                target_file = os.path.join(target_dir, f)
                # 建 0 字节文件
                with open(target_file, "w", encoding="utf-8") as file:
                    pass
                file_count += 1
            
            # 控制台每克隆几百个输出一下
            if file_count % 500 == 0 and file_count > 0:
                print(f"   已扫描并生成: {file_count} 个空文件的骨架...")
                
    except PermissionError as pe:
        print(f"⚠️ 权限受限跳过部分目录: {pe}")
    except Exception as e:
        print(f"❌ 克隆过程中发生异常: {e}")

    cost = time.time() - start_time
    print(f"✅ 【第二试验田 (Real Mirror Sandbox)】 克隆完毕！")
    print(f"   总耗时: {cost:.2f} 秒")
    print(f"   镜像包含: {folder_count} 个文件夹骨架, {file_count} 个空文件 (0 字节)")
    print(f"   目标沙盒位置: {dst_root}")

if __name__ == "__main__":
    create_mirror(NAS_REAL_ROOT, SANDBOX_REAL_DIR)
