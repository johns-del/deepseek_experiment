# 导入 tkinter 模块，并通常将其重命名为 tk 以方便使用
import tkinter as tk
# 导入 tkinter.messagebox 模块，用于显示简单的消息框
import tkinter.messagebox

# --- 回调函数 ---
# 这个函数将在按钮被点击时调用
def show_message():
  """当按钮被点击时，弹出一个信息提示框"""
  # 使用 messagebox 显示一个简单的信息框
  # 第一个参数是标题，第二个参数是消息内容
  tk.messagebox.showinfo("提示", "你好，世界！你点击了按钮。")

# --- 主程序 ---
# 1. 创建主窗口 (根窗口)
# 这是所有其他 GUI 元素的容器
root = tk.Tk()

# 2. 设置窗口属性
root.title("简单的 Tkinter 示例") # 设置窗口顶部的标题文字
root.geometry("400x300") # 设置窗口的初始大小 (宽度 x 高度)

# 3. 创建组件 (Widgets)
# 创建一个标签 (Label) 组件
# 第一个参数是父容器 (这里是主窗口 root)
# text 参数设置标签显示的文本
welcome_label = tk.Label(root, text="欢迎使用 Tkinter!", font=("Arial", 16))

# 创建一个按钮 (Button) 组件
# command 参数指定了当按钮被点击时要调用的函数 (这里是 show_message)
# 注意：这里传递的是函数名 show_message，而不是 show_message()
click_button = tk.Button(root, text="点我！", command=show_message, width=10, height=2)

# 4. 放置组件 (使用布局管理器)
# 使用 pack() 布局管理器将组件添加到窗口中
# pack() 会自动调整组件大小并将其放置在可用空间中
# pady 参数在组件的上方和下方添加一些垂直填充（边距）
welcome_label.pack(pady=20)
click_button.pack(pady=10)

# 5. 启动 Tkinter 事件循环
# mainloop() 会让窗口保持显示状态，并监听用户的操作 (如点击按钮、关闭窗口等)
# 程序会一直停留在这里，直到窗口被关闭
root.mainloop()

# 当窗口关闭后，mainloop() 结束，程序继续执行到这里 (如果有后续代码的话)
print("Tkinter 窗口已关闭。")