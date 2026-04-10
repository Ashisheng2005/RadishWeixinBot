from wxauto import WeChat

wx = WeChat()

wx.SendMsg("你好", who="胡兆俊")

msgs = wx.GetAllMessage()
for msg in msgs:
    print(msg)