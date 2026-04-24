from wxauto import WeChat
from wxauto.msgs import FriendMessage
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class WeChatBot:
    """对wxauto的封装，支持多监听、自动清理与日志记录"""
    def __init__(self):
        self.wx = WeChat()
        self.listeners = {}

    def add_listener(self, nickname, callback):
        """添加监听器"""
        self.listeners[nickname] = callback
        self.wx.AddListenChat(nickname=nickname, callback=callback)
        logger.info(f"已添加监听: {nickname}")

    def remove_listener(self, nickname):
        """移除监听器"""
        if nickname in self.listeners:
            self.wx.RemoveListenChat(nickname=nickname)
            del self.listeners[nickname]
            logger.info(f"已移除监听: {nickname}")

    def run(self):
        try:
            if not self.listeners:
                self.add_listener("张三", on_message)
            self.wx.KeepRunning()
        except Exception as e:
            logger.error(f"运行异常: {e}")
            for nick in list(self.listeners.keys()):
                self.remove_listener(nick)


def on_message(msg, chat):
    """默认消息处理函数"""
    with open("msgs.txt", "a", encoding="utf-8") as f:
        f.write(msg.content + "\n")
    if msg.type in ("image", "video"):
        logger.info(f"已下载媒体: {msg.download()}")
    if isinstance(msg, FriendMessage):
        msg.quote("收到")


if __name__ == "__main__":
    bot = WeChatBot()
    bot.run()
