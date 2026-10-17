---
name: Amazon purchase
description: >-
  Use this when buying a specific product on Amazon.com after the user confirmed
  the item and spend.
---
# Amazon purchase

Buy one confirmed product on Amazon.com. Research and product choice happen before this skill. Never place an order without an explicit user yes for that item and spend.

## Before dispatch

1. Confirm the exact product (title, ASIN or product URL, qty, one-time vs Subscribe & Save).
2. Confirm spend approval for this purchase only.
3. Read `box-desktop` and `in-chat-forms` before any browser or login form work.
4. Prefer a connected password manager via `ListCredentials` on `amazon.com`. If none is connected, use `request_user_form` with live snapshot refs. Never ask for passwords in chat.
5. Amazon sign-in is multi-step. One form per step: email/mobile first, then password, then OTP only if shown.

## Fastest path

Open the exact product URL (or `https://www.amazon.com/dp/<ASIN>`). Do not rebuild the listing through search when you already have the URL or ASIN.

## Dispatch snippet

Paste into the computerUse Task (fill the placeholders):

```
Purchase this exact Amazon product.
URL: <product URL>
ASIN: <ASIN if known>
Title check: <short expected title>
Qty: <n>
Purchase type: one-time (avoid Subscribe & Save unless user asked)

User explicitly approved this purchase.

1. Open the product URL directly.
2. Confirm title/ASIN match. Stop if wrong item or a substitute.
3. If signed out, stop on the first visible login step and report URL + field refs + Continue/Sign-in button refs. Do not type credentials.
4. If OTP, captcha, passkey, or 3DS appears, stop and report clearly.
5. Add qty, choose one-time purchase, proceed to checkout.
6. Before Place Order, report shipping name/city/state/ZIP, payment last4 if shown, item, qty, and order total. If shipping is wrong for this user, STOP.
7. Place Order only when product, qty, one-time, shipping, and payment look correct.
8. Return order number, total, estimated delivery, and shipping name/city.

Ground rules: work in one tab; one fresh snapshot after each navigation or click; never invent credentials; never buy a different ASIN; never join Prime only to complete the order.
```

## After each login step

1. Take a fresh snapshot.
2. Call `request_user_form` only for fields visible now, with `domain: amazon.com` and targets from that snapshot.
3. After the fill receipt, snapshot again, then click Continue / Sign in via computerUse.
4. Repeat for password or OTP. For a one-shot OTP page, `submitAfterFill: true` is allowed.

## After purchase

Tell the user: order number, item, qty, total, payment last4 if known, shipping city, and ETA. Save durable household Amazon defaults (account name on shipping, city/ZIP) to memory only when observed and confirmed by a successful order.
