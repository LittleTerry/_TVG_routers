import requests
import sys

# --- 第一步：获取端口（找门牌号） ---
# 默认是 8188，如果启动命令里有 --port，就抓取实际的
port = "8188"
if "--port" in sys.argv:
    idx = sys.argv.index("--port")
    port = sys.argv[idx + 1]

# --- 第二步：处理输入信号（看保险开关） ---
# 无论 any1 传进来的是布尔值 (True/False) 还是字符串 ("True")
# 我们先用 str() 把它变文字，再用 .lower() 把它变小写
input_signal = str(any1).lower()

# 在控制台打印一下，方便我们调试观察
print(f"\n收到信号内容: {any1}，端口为: {port})\n")

# --- 第三步：逻辑判断（决定动不动手） ---
# 只有当信号变成小写后等于 "true"，才执行重启
if input_signal == "true":
    print(f"【验证通过】信号为 {input_signal}，准备重启 ComfyUI...")
    
    url = f"http://127.0.0.1:{port}/manager/reboot"
    try:
        # 发送重启指令
        requests.post(url)
        print(">>> 重启指令已成功发送！")
    except Exception as e:
        print(f">>> 发送失败，原因：{e}")
else:
    # 如果信号不是 true，就什么都不做
    print(f"【安全拦截】信号为 {input_signal}，不执行重启操作。")
