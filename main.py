from wxauto import WeChat
from wxauto.msgs import FriendMessage
import time

wx = WeChat()

# 消息处理函数
def on_message(msg, chat):
    # 示例1：将消息记录到本地文件
    with open('msgs.txt', 'a', encoding='utf-8') as f:
        f.write(msg.content + '\n')

    # 示例2：自动下载图片和视频
    if msg.type in ('image', 'video'):
        print(msg.download())

    # 示例3：自动回复收到
    if isinstance(msg, FriendMessage):
        msg.quote('收到')



def listener():
    try:
        # 添加监听，监听到的消息用on_message函数进行处理
        wx.AddListenChat(nickname="张三", callback=on_message)

        # 保持程序运行
        wx.KeepRunning()
    except Exception as e:
        wx.RemoveListenChat(nickname="张三")
        print(e)


if "__main__" == __name__:
    listener()