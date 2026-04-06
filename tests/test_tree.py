# 文件路径: test_tree.py
import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Treeview 测试")
    root.geometry("400x300")

    tree = ttk.Treeview(root, columns=("col1",), show="headings")
    tree.heading("col1", text="测试列")
    tree.column("col1", width=200, anchor=tk.CENTER)
    tree.pack(fill=tk.BOTH, expand=True)

    for i in range(5):
        tree.insert("", tk.END, values=(f"测试行 {i+1}",))

    root.mainloop()

if __name__ == "__main__":
    main()