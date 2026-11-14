# 健人餐廚巨蛋店｜LINE 加好友落地頁

Meta 廣告（流量目標）導向本頁，再引導訪客加入 LINE 官方帳號。

- 官方帳號：健人餐廚-健康餐（巨蛋店）
- Basic ID：`@071bizxl`
- 加好友連結：https://line.me/R/ti/p/@071bizxl

## 廣告網址

請在 Ads Manager 把目的地網址設成（把網域換成實際上線後的網址）：

```
https://jianren-line.onrender.com/?utm_source=meta&utm_medium=paid&utm_campaign=jianren_test&utm_content={{ad.name}}
```

頁面會把 UTM 與 `fbclid` 存進 localStorage，並附加到 LINE 加好友連結。點擊綠色按鈕時會先送出 Meta 像素的 `Lead` 與自訂事件 `ClickLINE`，約 300 毫秒後再跳轉。

首購優惠文案請把頁面上的 `[優惠內容待填]` 換成實際內容後再投放。
