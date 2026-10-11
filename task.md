# BEW Project — Supervisor Task & Review Board

> **ভূমিকা:** এটি সুপারভাইজর রিভিউ বোর্ড। এজেন্টরা যা কাজ করবে, এখানে তাদের ভুল ধরা হবে এবং নতুন কাজের নির্দেশনা দেওয়া থাকবে।
> 
> 🛑 **কঠোর সতর্কবার্তা (STRICT RULE FOR ALL AGENTS):**
> **কোনো এজেন্টের জন্য `git commit` বা `git push` করা সম্পূর্ণ নিষিদ্ধ (হারাম)!**
> কোনো অবস্থাতেই কোনো সাব-এজেন্ট বা কোঅর্ডিনেটর কমিট বা পুশ চালাবে না। আপনারা শুধু কোড এডিট ও টেস্ট করবেন।
> সমস্ত পরিবর্তন অডিট ও যাচাই-বাছাই শেষে **শুধুমাত্র সুপারভাইজর নিজে কমিট ও পুশ করবে।**

---

## 🎯 বর্তমান অগ্রাধিকার ও কাজের তালিকা (Priorities for Agents)

### ১. ফ্রন্ট-এন্ড "জমির সীমানা মেজারমেন্ট" (CSS Layout Boundary & Viewport)
- [x] **সমস্যা:** ড্যাশবোর্ড সাইডবারে উইন্ডোজের ১৭px মোটা নেটিভ স্ক্রলবার চলে আসছে, নিচের আইটেম ("Shops", "Categories") আধা কেটে যাচ্ছে।
- [x] **সমাধান নির্দেশ:**
  - `web/static/css/tokens.css` এবং `web/static/css/components.css`-এ কাস্টম স্লিক স্ক্রলবার (`scrollbar-width: thin;`, `::-webkit-scrollbar`) কনফিগার করা হয়েছে।
  - রুট অ্যাপ শেলকে `height: 100dvh; overflow: hidden;` দিয়ে শক্ত সীমানা দেওয়া হয়েছে।
  - সাইডবারের ইনলাইন `:style="window.innerWidth >= 768 ? ..."` বাদ দিয়ে পিওর রেসপন্সিভ Tailwind/CSS ক্লাসে কনভার্ট করা হয়েছে।
  - মোবাইলে সাইডবার ড্রয়ার ওপেন থাকলে ক্লোজ আইকন (`close`) দেখানো হয়েছে।

### ২. PageSpeed Insights `NO_FCP` সমাধান
- [x] **সমস্যা:** মোবাইলে লাইটহাউস বট `NO_FCP` এরর দিচ্ছে।
- [x] **সমাধান নির্দেশ:**
  - `web/templates/layout.html`-এ `body` ট্যাগে `.alpine-loading { opacity: 0; }` অপসারিত। পেজ এখন তাৎক্ষণিক পেইন্ট হয়।

### ৩. ইউনিভার্সাল টোস্ট হাব (Toast Notification Hub)
- [x] ফ্ল্যাশ মেসেজ ও ডায়নামিক অ্যালার্টগুলোর জন্য একটি ইউনিভার্সাল টোস্ট স্টোর (`Alpine.store('toast')`), `_notifications.html` এবং `src/helpers/toast.py` ব্রিজ তৈরি ও অডিট পাস করেছে।

### ৪. মোবাইল PageSpeed অপ্টিমাইজেশন (Score 68 -> 74+ Boost)
- [x] **অডিট ইনসাইট (DevTools Console হতে প্রাপ্ত):**
  - রেন্ডার ব্লকিং রিকোয়েস্টের কারণে মোট ~৩,৫৮০ms নষ্ট হচ্ছিল।
  - `Material Icons` ফন্টে `&display=swap` মিসিং ছিল।
  - `logo.svg` ফাইলে এক্সপ্লিসিট `width` এবং `height` দেওয়া ছিল না।
  - `logo.svg` ফাইলটির সাইজ প্রায় ২৮৭ KB ছিল।
- [x] **সমাধান নির্দেশ (Tasks for Agents):**
  1. `web/templates/layout.html`-এ Material Icons লিংকে `&display=swap` নিশ্চিত করা হয়েছে এবং `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>` যোগ করা হয়েছে।
  2. `web/templates/dashboard_base.html` এবং অন্যান্য টেমপ্লেটে `<img src="...logo.svg">` ট্যাগে সরাসরি `width="28" height="28"` এবং `loading="eager"` দেওয়া হয়েছে।
  3. `web/static/img/logo.svg` ফাইলের সাইজ ২৮৬ KB থেকে ১৭৭ KB-তে কমিয়ে অপ্টিমাইজ করা হয়েছে (-৩৮%)।

---

## 🔍 এজেন্টদের কাজের অডিট ও ফিডব্যাক লগ (Review Notes)

*এখনও কোনো রিমোট পুশ পাওয়া যায়নি। প্রতি ৫ মিনিট পরপর গিট ফেচ করে নতুন কোড অডিট করা হবে এবং কড়া রিভিউ কমেন্ট এখানে যোগ করা হবে।*

- **[Check @ 18:20 (Iteration 1)]:** `git fetch origin development` সম্পন্ন। নতুন কোনো পুশ পাওয়া যায়নি (লাস্ট কমিট: `f7f2350`)। এজেন্টরা কাজ করছে, পরবর্তী চেকের জন্য অপেক্ষা করছি।

- **[Coordinator @ polling]:** ৫ মিনিটের timer চালু (`Start-Sleep 300`, shell `sh_12aea8c06001xJg5gfslsDkr60`)। আমি নিজে কোডে হাত দেবো না — সময় শেষ হলে task.md পড়ে ছোট এজেন্টদের দিয়ে করাবো, ওদেরকেও ৫ মিনিটের timer + task.md পড়ার নির্দেশ দেবো।
- **[Supervisor Directive @ 18:24]:** কোঅর্ডিনেটর ও সমস্ত সাব-এজেন্টদের জানানো হচ্ছে — আপনারা শুধু কোড এডিট ও ভ্যালিডেট করবেন। **`git commit` এবং `git push` সম্পূর্ণ হারাম ও নিষিদ্ধ।** সমস্ত কাজ সম্পন্ন হলে সুপারভাইজর প্রতিটি ফাইলের ডিফারেন্স ও আর্কিটেকচার অডিট করে নিজে চূড়ান্ত কমিট ও পুশ দেবে।
- **[Check @ 18:25 (Iteration 2)]:** লোকাল এবং রিমোট অডিট সম্পন্ন। এখনো কোনো কোড ফাইলে পরিবর্তন আসেনি। কোঅর্ডিনেটরের ৩শ সেকেন্ডের স্লিপ চলছে, সাব-এজেন্টরা কাজ শুরু করলে পরবর্তী চেক (১৮:৩০)-এ ধরা হবে।
- **[Coordinator @ 18:27 (Iteration 3)]:** ৩ জন ছোট এজেন্ট কাজ শেষ করেছে, commit/push করেনি (directive মানা)। Timer `sh_12aea8c06001xJg5gfslsDkr60` শেষ (18:27:57)। Changes: P1 tokens/components/dashboard_base (scrollbar+app-shell+sidebar reactive+close icon), P2 layout.html NO_FCP (alpine-loading বাদ, x-cloak only), P3 toast hub (alpine-store toast + _notifications.html + src/helpers/toast.py + main.py bridge)। `git status` verified। Side-note: `data/shop.db` + logs touched (test-client side effect) — supervisor audit করবে। পরের ৫ মিনিটের timer চালু।

- **[Senior Supervisor Review @ 18:32 (Iteration 3 Audit)]:**
  গিট ডিফ এবং এএসটি লিন্টার চালিয়ে ছোট এজেন্টদের কোড অডিট করা হলো। ফ্রন্ট-এন্ডে ভালো কাজ হয়েছে, কিন্তু পাইথন কোডে নিয়মের মারাত্মক ব্যত্যয় ঘটেছে:

  1. **👍 যা ঠিক হয়েছে (Pass):**
     - `tokens.css` এবং `components.css`-এ `100dvh` রুট শেল ও `slick-scroll` দিয়ে উইন্ডোজের মোটা ১৭px স্ক্রলবার হটানো হয়েছে।
     - `dashboard_base.html`-এ ইনলাইন `window.innerWidth` বাদ দিয়ে পিওর CSS ক্লাস ও ক্লোজ আইকন বসানো হয়েছে।
     - `layout.html`-এ `alpine-loading { opacity: 0; }` ব্লকার তুলে দিয়ে FCP আনব্লক করা হয়েছে।

  2. **❌ ধুর মিয়া! এই ভুলগুলো কে করলো?! অবিলম্বে ঠিক করো (Action Required):**
     - **ভুল ১ (ডকস্ট্রিং/কমেন্ট অপরাধ):** `src/helpers/toast.py`-তে ১৫ লাইনের রচনা/ডকস্ট্রিং আর ফাংশন ডকস্ট্রিং লিখে কেন ভরিয়েছো?! নিয়মে স্পষ্ট বলা আছে: *"Do not use comments or docstrings inside code. Excessive comments consume AI tokens."* সব ডকস্ট্রিং ও ইনলাইন কমেন্ট মুছে কোড ক্লিন করো।
     - **ভুল ২ (লগিং নিয়ম লঙ্ঘন):** `toast.py`-তে `app.logger.exception` ব্যবহার করলা কোন আক্কেলে? প্রজেক্টে সেন্ট্রালাইজড লগার আছে: `from src.config import setup_logger, Settings` দিয়ে `logger = setup_logger(Settings.LOG_DIR / "helpers.log", name="bew.helpers.toast")` ব্যবহার করো!
     - **ভুল ৩ (টাইপ সেফটি ও ব্রাঞ্চিং):** `_pop_flashes()`, `_merge_trigger_header()`, `register_toast_bridge()`-এ কোনো টাইপ হিন্ট নাই! স্ট্রিক্ট টাইপিং যুক্ত করো এবং `isinstance(payload['bewToast'], list)` টাইপ ব্রাঞ্চিং স্মেল ঠিক করো।
     - **ভুল ৪ (ইমপোর্ট আর্কিটেকচার ভঙ্গ):** `main.py`-এর মাঝখানে গিয়ে `from src.helpers.toast import register_toast_bridge` করছো কেন?! `src/helpers/__init__.py`-তে `register_toast_bridge` এক্সপোর্ট করো, আর `main.py`-তে অন্যান্য হেল্পারের সাথে ওপরের ইমপোর্ট ব্লকে নিয়ে আসো। কোনো ব্যানার কমেন্ট রাখা যাবে না।

  👉 **নির্দেশনা:** ছোট এজেন্টরা দ্রুত এই ৪টি পয়েন্ট ঠিক করে ফাইল সেভ করুক। আমি পরবর্তী চেকের সময় আবার অডিট করব। সব ক্লিন হলে তবেই আমি ফাইনাল কমিট-পুশ দেব।
- **[Check @ 18:35 (Iteration 4)]:** অডিট চেক সম্পন্ন। ছোট এজেন্টরা অ্যাকশন আইটেমগুলোর ওপর কাজ করছে। পরবর্তী চেক (১৮:৪০)-এ সংশোধিত কোড পুনঃযাচাই করা হবে।
- **[Coordinator @ 18:36]:** ৪ পয়েন্টের fix শেষ (১ জন agent): toast.py docstring/comment মুছেছে, centralized logger (`bew.helpers.toast`), strict typing + isinstance smell fix, `__init__.py` export + main.py top import। No commit/push। py_compile + import verified। পরের timer চালু।
- **[Coordinator @ 18:41]:** Timer শেষ, task.md পড়লাম — নতুন নির্দেশনা নেই। `git status` আগের মতোই (P1+P2+P3 changes + toast fix, no commit)। পরের ৫ মিনিটের timer চালু।
- **[Senior Supervisor Review @ 18:40 (Iteration 5 Audit)]:**
  সংশোধিত কোড পুনঃঅডিট করা হলো:
  1. `src/helpers/toast.py`: ডকস্ট্রিং ও অপ্রয়োজনীয় কমেন্ট সফলভাবে অপসারিত। সেন্ট্রালাইজড লগার (`bew.helpers.toast`) এবং টাইপ হিন্ট যুক্ত হয়েছে।
  2. `src/helpers/__init__.py`: `register_toast_bridge` সিঙ্গেল এক্সপোর্ট পয়েন্টে যুক্ত হয়েছে।
  3. `main.py`: টপ-লেভেল ইমপোর্টে সঠিকভাবে আনা হয়েছে।
  4. টেস্ট স্যুট: ৬২টি টেস্ট রান করে ১০০% পাস করেছে (`62 passed`).
  
  ✅ **সার্বিক ফলাফল:** ৪টি অ্যাকশন আইটেমই সফলভাবে ফিক্স হয়েছে। ফ্রন্ট-এন্ড স্ক্রলবার/লেআউট এবং ব্যাক-এন্ড টোস্ট হাব উভয়ই উত্তীর্ণ। কাজ সম্পূর্ণ প্রস্তুত।
- **[Coordinator @ 18:46]:** Timer sesh, Supervisor Review (18:40) dekhlam — sob pass, 62 tests green. Notun kaj nei, kichu dispatch korini. No commit/push. Porer timer chalu.
- **[Senior Supervisor Review @ 18:50 (Iteration 6/7 — DevTools Console Audit)]:**
  Chrome DevTools Console দিয়ে লাইভ PageSpeed রিপোর্ট ডিবাগ করে নতুন লাইভ টেস্ট রান করা হয়েছে (সন্ধ্যা ৬:৪৬-এর রিপোর্ট):
  - **নতুন লাইভ স্কোর:** Performance: **68** 🟡 (আগের NO_FCP সম্পূর্ণ দূর হয়েছে!), Accessibility: **96** 🟢, Best Practices: **100** 🟢, SEO: **91** 🟢, TBT: **0ms** 🟢, CLS: **0.003** 🟢!
  - **কনসোল থেকে প্রাপ্ত বটলনেক:** মোট ৩,৫৮০ms রেন্ডার ব্লকিং রিকোয়েস্ট আছে (Material Icons ফন্টে &display=swap নেই [752ms], logo.svg-তে কোনো নির্দিষ্ট width/height নেই এবং সাইজ ২৮৭ KB!)।
  👉 **নতুন অ্যাসাইনমেন্ট:** প্রায়োরিটি সেকশন ৪ (P4)-এ উল্লেখিত ৩টি অপ্টিমাইজেশন টাস্ক ছোট এজেন্টদের দিয়ে দ্রুত বাস্তবায়ন করা হোক। কোনো কমিট বা পুশ চলবে না।
- **[Coordinator @ 18:52]:** P4 done (1 agent): layout.html display=swap + preconnect gstatic, logo img width/height/loading (dashboard 28, navbar 85, footer 28), logo.svg 286533 -> 177934 bytes (-38%). No commit/push. Porer timer chalu.
- **[Senior Supervisor Review @ 18:57 (Iteration 8 — Post-P4 Live Audit)]:**
  Post-P4 অপ্টিমাইজেশন শেষে PageSpeed Insights-এ লাইভ টেস্ট আবার রান করা হলো (সন্ধ্যা ৬:৫৬-এর রিপোর্ট):
  - **স্কোর অগ্রগতি:** Mobile Performance **৬৮ থেকে বৃদ্ধি পেয়ে ৭৪-এ উন্নীত হয়েছে (+৬ পয়েন্ট বৃদ্ধি!)** 🎉
  - **অন্যান্য স্কোর:** Accessibility: **96** 🟢, Best Practices: **100** 🟢, SEO: **91** 🟢, Agentic Browsing: **2/2** 🟢, TBT: **0ms** 🟢, CLS: **0** 🟢!
  ✅ **সার্বিক মূল্যায়ন:** P4-এর সমস্ত অপ্টিমাইজেশন (font swap, explicit dimensions, svg trim) সফলভাবে কাজ করেছে এবং স্কোর সরাসরি ৭৪-এ পৌঁছেছে। কোড সম্পূর্ণ স্থিতিশীল ও টেস্ট পাস।
- **[Coordinator @ 18:58]:** Timer sesh, Review (18:57) dekhlam — Performance 68 -> 74 (+6), baki sob green. Notun kaj nei. No commit/push. Porer timer chalu.
- **[Senior Supervisor Review @ 19:00 (Iteration 9)]:**
  অডিট রিভিউ অব্যাহত রয়েছে। সকল ফ্রন্ট-এন্ড আর্কিটেকচার, স্ক্রলবার ফিক্স, FCP অপ্টিমাইজেশন ও টোস্ট হাব সম্পূর্ণ স্থিতিশীল এবং কোনো এরর বা রিগ্রেশন নেই। ব্যবহারকারীর অনুমতি সাপেক্ষে চূড়ান্ত কমিট ও পুশের জন্য প্রস্তুত।
- **[Coordinator @ 19:03]:** Timer sesh, Review (19:00) dekhlam — sob stable, commit/push er jonno user permission er opekkha. Notun kaj nei. No commit/push. Porer timer chalu.
