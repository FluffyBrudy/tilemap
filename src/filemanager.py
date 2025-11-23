from tkinter import Tk, filedialog


def openfilemanager():
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename()
    root.destroy()
    return file_path
