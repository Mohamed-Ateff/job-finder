"use strict";
/* Arabic for the whole interface. Keys are the English text; anything missing falls back to English.
   {name}-style placeholders are filled by t(). Job titles, company names and posting text stay as posted. */

window.AR = {
  // dates
  "Today": "اليوم", "Yesterday": "أمس", "{day} at {time}": "{day}، {time}",
  "Previous 7 Days": "آخر 7 أيام", "Previous 30 Days": "آخر 30 يوماً",

  // pages and navigation
  "Jobs": "الوظائف", "Client Setup": "إعداد العميل", "Search Profile": "ملف البحث", "How It Works": "كيف يعمل",
  "Setup": "الإعداد", "Profile": "الملف", "Guide": "الدليل", "Help": "المساعدة",
  "Switch person": "تبديل الشخص", "Automatic": "تلقائي", "Light": "فاتح", "Dark": "داكن",
  "Appearance": "المظهر", "Language": "اللغة",
  "Matches": "المطابقة", "All": "الكل", "Applied": "تم التقديم",
  "Strong": "قوي", "Good": "جيد", "Moderate": "متوسط", "Weak": "ضعيف",

  // toolbar and status
  "Search": "بحث", "Search for new jobs now": "ابحث عن وظائف جديدة الآن", "Running": "جارٍ البحث", "Run Search": "ابدأ البحث",
  "No jobs yet": "لا توجد وظائف بعد", "Everything about how the app works": "كل شيء عن طريقة عمل التطبيق",
  "{n} still needed": "{n} متبقية", "Everything is ready": "كل شيء جاهز",
  "{m} · {all} scored · {applied} applied": "المطابقة {m} · المقيّمة {all} · تم التقديم {applied}",
  "{m} · {all} scored": "المطابقة {m} · المقيّمة {all}",
  "Search activity": "نشاط البحث", "Scheduled search running…": "بحث مجدول قيد التشغيل…",
  "Search finished": "اكتمل البحث", "Search stopped": "توقف البحث", "Last search {when}": "آخر بحث: {when}",
  "No searches yet": "لا توجد عمليات بحث بعد", "Working": "جارٍ العمل",
  "Finding new postings": "البحث عن إعلانات جديدة", "Filtering and removing duplicates": "تصفية الإعلانات وحذف المكرر",
  "Scoring jobs against the profile": "تقييم الوظائف مقارنةً بالملف المهني", "Preparing CVs": "تجهيز السير الذاتية",
  "Saving the results": "حفظ النتائج",
  "Filter": "التصفية", "Score": "التقييم", "CVs": "السير الذاتية", "Save": "حفظ",

  // demo mode
  "<b>Demo Mode</b> — sample jobs and a simulated AI. Nothing is emailed, and your real data isn’t touched.":
    "<b>الوضع التجريبي</b> — وظائف تجريبية وذكاء اصطناعي محاكى. لا يُرسل أي بريد، ولا تُمس بياناتك الحقيقية.",
  "Reset Demo": "إعادة ضبط التجربة", "Turn Off": "إيقاف",
  "Demo Mode On": "تم تشغيل الوضع التجريبي", "Demo Mode Off": "تم إيقاف الوضع التجريبي", "Demo Reset": "أُعيد ضبط التجربة",

  // notices
  "Dismiss": "إغلاق", "{n} KB": "{n} كيلوبايت", "{n} bytes": "{n} بايت",
  "Saved": "تم الحفظ", "Marked as Applied": "تم وضع علامة التقديم", "Search Finished": "اكتمل البحث", "Digest Sent": "أُرسل الملخص",
  "ChatGPT On": "تم تشغيل ChatGPT", "Free Mode": "الوضع المجاني", "Copied": "تم النسخ", "Exported": "تم التصدير",
  "Another search for this person was already running.": "كان هناك بحث آخر لهذا الشخص قيد التشغيل.",
  "The search stopped: {reason}.": "توقف البحث: {reason}.",
  "The search stopped. Open the activity view to see the log.": "توقف البحث. افتح نافذة النشاط لعرض السجل.",

  // job list
  "No Results": "لا توجد نتائج", "Nothing matches “{q}”.": "لا شيء يطابق «{q}».",
  "No Strong Matches Yet": "لا توجد وظائف قوية بعد",
  "{jobs} scored so far, none at {good} or above.": "قُيّمت {jobs} حتى الآن، ولم تبلغ أيٌّ منها {good} أو أكثر.",
  "Show All Jobs": "عرض كل الوظائف", "Nothing Applied Yet": "لم تتقدّم لأي وظيفة بعد",
  "After you apply for a job, press Mark as Applied on it. It will be listed here, so you never apply twice.":
    "بعد التقديم على وظيفة، اضغط «وضع علامة التقديم» عليها، فتظهر هنا ولن تتقدّم لها مرتين.",
  "Roles that fit {name} will appear here, each with its job link, a score and a CV.":
    "ستظهر هنا الوظائف المناسبة لـ{name}، ولكلٍّ منها رابط الإعلان ودرجة توافق وسيرة ذاتية.",
  "Run a Search": "ابدأ البحث", "Try a Demo Search": "جرّب بحثاً تجريبياً",
  "See how matches, scores and CVs look for {name}, using sample jobs.":
    "شاهد كيف تبدو الوظائف المطابقة والدرجات والسير الذاتية لـ{name} باستخدام وظائف تجريبية.",
  "No Jobs Yet": "لا توجد وظائف بعد", "Finish Client Setup, then run the first search.": "أكمل إعداد العميل، ثم ابدأ أول بحث.",
  "Open Client Setup": "فتح إعداد العميل", "Try Demo Mode": "تجربة الوضع التجريبي",
  "Sample job": "وظيفة تجريبية", "CV ready": "السيرة جاهزة", "Select a Job": "اختر وظيفة",
  "{matches} found": "عُثر على {matches}", "Nothing new this time": "لا جديد هذه المرة", "Preview": "معاينة",
  "{jobs} scored": "قُيّمت {jobs}", "Stopped before scoring": "توقف قبل التقييم",

  // job detail
  "A strong fit. Worth applying today.": "توافق قوي، تستحق التقديم اليوم.",
  "A good fit. Worth a careful look.": "توافق جيد، تستحق نظرة متأنية.",
  "Partly fits. Read the posting before applying.": "تناسب جزئياً، اقرأ الإعلان قبل التقديم.",
  "Not a fit for this profile.": "لا تناسب هذا الملف المهني.",
  "{verdict} fit": "توافق {verdict}",
  "Keyword match": "تطابق الكلمات", "Interview fit": "ملاءمة المقابلة",
  "How many of the profile’s skills and field terms the posting mentions": "عدد مهارات الملف المهني ومصطلحات مجاله التي يذكرها الإعلان",
  "Whether the title and level match roles the profile can defend": "مدى تطابق المسمّى والمستوى مع أدوار يستطيع الملف المهني إثباتها",
  "Best CV track": "أنسب مسار مهني", "Also fits": "يناسب أيضاً", "CV": "السيرة الذاتية", "Ready to download": "جاهزة للتنزيل",
  "Not written (CVs are prepared for Good and Strong fits)": "لم تُكتب (تُجهَّز للوظائف الجيدة والقوية)",
  "Application": "التقديم", "Applied {when}": "تم التقديم {when}", "Not applied yet": "لم يتم التقديم بعد",
  "Found": "تاريخ العثور", "{when} on {site}": "{when} على {site}",
  "Sample Posting": "إعلان تجريبي", "Demo Mode uses sample jobs, so there is no real posting": "يستخدم الوضع التجريبي وظائف تجريبية، فلا يوجد إعلان حقيقي",
  "Apply on {site}": "قدّم عبر {site}", "Download CV": "تنزيل السيرة الذاتية", "Mark as Applied": "وضع علامة التقديم",
  "Click to clear the mark": "اضغط لإزالة العلامة", "Mark this job once you’ve sent your application": "ضع العلامة بعد إرسال طلبك",
  "About the Role": "عن الوظيفة", "Why It Fits": "لماذا تناسب", "Details": "التفاصيل",
  "Jobs that score below {n} are kept without a written summary.": "الوظائف التي تقل درجتها عن {n} تُحفظ دون ملخص مكتوب.",

  // client setup
  "{name}’s search needs a few things from the client before it can run on its own every morning.":
    "يحتاج بحث {name} إلى بعض الأمور من العميل قبل أن يعمل تلقائياً كل صباح.",
  "Everything {name}’s search needs is in place. It can run every morning on its own.":
    "كل ما يحتاجه بحث {name} جاهز، ويمكنه العمل تلقائياً كل صباح.",
  "{done} of {total} ready": "{done} من {total} جاهزة", "All set": "كل شيء جاهز", "{ok} of {n}": "{ok} من {n}",
  "Optional": "اختياري", "Not accepted": "غير مقبول", "Not added": "غير مضاف", "None": "لا يوجد",
  "Find it in {where}.": "تجده في {where}.", "Paste the key": "الصق المفتاح", "Cancel": "إلغاء", "Checking": "جارٍ التحقق",
  "Done: {title}": "تم: {title}",

  // search profile
  "How {name}’s daily search is set up, and exactly what the AI reads.": "طريقة إعداد البحث اليومي لـ{name}، وما يقرؤه الذكاء الاصطناعي بالضبط.",
  "The tracks and keywords are drafts until the client approves them.": "المسارات والكلمات المفتاحية مسودّات حتى يوافق عليها العميل.",
  "Location": "الموقع", "Seniority": "المستوى الوظيفي", "Job sites": "مواقع الوظائف", "Keywords": "الكلمات المفتاحية",
  "CV Tracks": "المسارات المهنية", "The AI picks one for each job": "يُختار مسار لكل وظيفة",
  "Leads with achievements {list} from the discovery record.": "يبدأ بالإنجازات {list} من سجل الاكتشاف.",
  "What the AI Reads": "ما يقرؤه الذكاء الاصطناعي", "Not exported yet": "لم يُصدَّر بعد",
  "See the knowledge base and prompts exactly as the AI receives them.": "اطّلع على قاعدة المعرفة والتعليمات كما يستلمها الذكاء الاصطناعي تماماً.",
  "No API calls, no cost.": "دون أي اتصال خارجي، ودون تكلفة.", "Export Again": "تصدير مجدداً", "Export": "تصدير", "Exporting": "جارٍ التصدير",
  "{n} characters, exactly as the AI receives them.": "{n} حرفاً، تماماً كما يستلمها الذكاء الاصطناعي.", "Done": "تم",
  "Saudi Arabia": "السعودية", "United Arab Emirates": "الإمارات", "Qatar": "قطر", "Kuwait": "الكويت", "Bahrain": "البحرين",
  "Oman": "عُمان", "Egypt": "مصر",
  "mid-senior": "متوسط إلى أول", "director": "مدير", "executive": "تنفيذي", "entry": "مبتدئ", "associate": "مساعد",

  // activity panel
  "Scheduled search running": "بحث مجدول قيد التشغيل",
  "It was started outside this app. Its jobs appear in Jobs when it finishes.": "بدأ من خارج التطبيق، وستظهر وظائفه في «الوظائف» عند اكتماله.",
  "Last search": "آخر بحث", "Jobs scored": "الوظائف المقيّمة", "Strong or good": "قوية أو جيدة", "CVs prepared": "السير الذاتية المُجهزة",
  "Show Jobs": "عرض الوظائف",
  "Run a preview to see what a daily search finds. Nothing is emailed.": "شغّل معاينة لترى ما يجده البحث اليومي، دون إرسال أي بريد.",
  "Run a search to see what it finds. Matches and CVs are saved here.": "ابدأ بحثاً لترى ما يجده، وتُحفظ الوظائف المطابقة والسير الذاتية هنا.",
  "Another search is running": "هناك بحث آخر قيد التشغيل", " · nothing was emailed": " · لم يُرسل أي بريد",
  "Show Log": "عرض السجل", "Hide Log": "إخفاء السجل", "{m} min {s} s": "{m} د {s} ث", "{s} s": "{s} ث",

  // run sheet
  "Run a Search for {name}": "بحث جديد لـ{name}", "Run a Demo Search for {name}": "بحث تجريبي لـ{name}",
  "Start Search": "بدء البحث", "Replay": "إعادة", "Replay Search": "إعادة البحث", "Start Preview": "بدء المعاينة",
  "Send": "إرسال", "Run and Send": "بحث وإرسال",
  "Finds today’s roles, scores them and writes a tailored CV for each strong match. Everything is saved here, ready for you to apply.":
    "يبحث عن وظائف اليوم ويقيّمها ويجهّز سيرة ذاتية لكل وظيفة مطابقة بقوة، ويحفظ كل شيء هنا جاهزاً للتقديم.",
  "Finds today's roles, scores them and writes the digest and CVs — without emailing anything.":
    "يبحث عن وظائف اليوم ويقيّمها ويكتب الملخص والسير الذاتية، دون إرسال أي بريد.",
  "Scores a search you've already run, without searching the job sites again. Only jobs that haven't been scored before are evaluated.":
    "يقيّم بحثاً أجريته سابقاً دون البحث في مواقع الوظائف مجدداً، ولا يُقيَّم إلا ما لم يُقيَّم من قبل.",
  "The full daily run: find, score, write CVs and email the digest.": "التشغيل اليومي الكامل: البحث والتقييم وكتابة السير الذاتية وإرسال الملخص بالبريد.",
  "The full daily run: find, score, write CVs and email the digest to {to}.": "التشغيل اليومي الكامل: البحث والتقييم وكتابة السير الذاتية وإرسال الملخص إلى {to}.",
  "Picks sample jobs, scores them with the simulated AI and writes the digest and CVs. Nothing is emailed.":
    "يختار وظائف تجريبية ويقيّمها بالذكاء الاصطناعي المحاكى ويكتب الملخص والسير الذاتية، دون إرسال أي بريد.",
  "Scores a sample search again. Only jobs that haven’t been scored before are evaluated.":
    "يعيد تقييم بحث تجريبي، ولا يُقيَّم إلا ما لم يُقيَّم من قبل.",
  "The full daily run with sample jobs. The digest is marked as sent in the demo data, but nothing is emailed.":
    "التشغيل اليومي الكامل بوظائف تجريبية؛ يُعتبر الملخص مُرسلاً في البيانات التجريبية دون إرسال أي بريد.",
  "Picks sample jobs, scores them with the simulated AI and writes a tailored CV for each strong match.":
    "يختار وظائف تجريبية ويقيّمها بالذكاء الاصطناعي المحاكى ويكتب سيرة ذاتية لكل وظيفة مطابقة بقوة.",
  "Saved search": "بحث محفوظ", "None yet": "لا يوجد بعد", "Score up to": "تقييم حتى", "All new jobs": "كل الوظائف الجديدة",
  "Write tailored CVs": "كتابة سير ذاتية مخصصة", "Email the digest": "إرسال الملخص بالبريد",
  "Mark the digest as sent": "اعتبار الملخص مُرسلاً", "Demo Mode — nothing is emailed": "الوضع التجريبي — لا يُرسل أي بريد",
  "To {to}": "إلى {to}", "No recipient set yet": "لم يُحدد مستلم بعد",
  "Add the {list} in {link} first.": "أضف {list} في {link} أولاً.",
  "A scheduled search is running right now. Try again when it finishes.": "يوجد بحث مجدول قيد التشغيل الآن. حاول مجدداً عند انتهائه.",
  "The score limit keeps the AI cost down; the job sites are still searched in full.":
    "حدّ التقييم يقلّل تكلفة الذكاء الاصطناعي، ومع ذلك يُبحث في مواقع الوظائف بالكامل.",
  "OpenAI API key": "مفتاح OpenAI", "Brevo API key": "مفتاح Brevo", "Sender address": "عنوان المُرسِل",
  "Recipient address": "عنوان المستلم", "working {x}": "{x} صالحاً",

  // login
  "Enter the password to continue.": "أدخل كلمة المرور للمتابعة.", "Password": "كلمة المرور", "Continue": "متابعة",
  "Can’t reach Job Automation": "تعذّر الوصول إلى التطبيق",

  // settings
  "Settings": "الإعدادات", "For the whole app and everyone in it": "للتطبيق كله ولكل من فيه", "General": "عام",
  "Last {period}": "آخر {period}", "Posted today": "نُشرت اليوم", "Posted yesterday": "نُشرت أمس", "Posted {n} days ago": "نُشرت قبل {n} أيام",
  "Posted": "تاريخ النشر", "Finding postings": "البحث عن الإعلانات", "Filtering": "التصفية", "Scoring": "التقييم",
  "Writing CVs": "كتابة السير الذاتية", "Saving": "الحفظ", "New": "جديدة", "Nothing new": "لا جديد", "The last search found no new jobs.": "لم يجد آخر بحث وظائف جديدة.",
  "Sample jobs and simulated scoring.": "وظائف تجريبية وتقييم محاكى.",
  "Appearance, language, how jobs are scored, and the rest. They apply to everyone in the app.":
    "المظهر واللغة وطريقة تقييم الوظائف وغيرها، وتنطبق على كل من في التطبيق.",
  "Job Search": "البحث عن الوظائف", "Look back": "مدة البحث", "How far back each search reads new postings.": "إلى أي مدى يعود كل بحث لقراءة الإعلانات الجديدة.",
  "24 hours": "24 ساعة", "3 days": "3 أيام", "7 days": "7 أيام",
  "Someone’s first search always looks back at least 3 days, so there’s something to see.":
    "أول بحث لأي شخص يعود 3 أيام على الأقل، حتى يجد ما يعرضه.",
  "Demo Mode": "الوضع التجريبي",
  "Try everything with sample jobs and simulated scoring. Real data isn’t touched.":
    "جرّب كل شيء بوظائف تجريبية وتقييم محاكى، دون المساس بالبيانات الحقيقية.",
  "Job Automation runs on this computer. Searching is free, and so is scoring unless ChatGPT is on.":
    "يعمل التطبيق على هذا الجهاز. البحث مجاني، والتقييم كذلك ما لم يكن ChatGPT مفعّلاً.",
  "Choose 24 hours, 3 days or 7 days": "اختر 24 ساعة أو 3 أيام أو 7 أيام",

  // people
  "Added in the app": "أُضيف من التطبيق", "New Profile…": "ملف جديد…", "From a questionnaire or a CV": "من استبيان أو سيرة ذاتية",
  "New Profile": "ملف جديد", "Start from a CV, or just a name. Everything can be changed afterwards.":
    "ابدأ من سيرة ذاتية أو باسم فقط، ويمكن تعديل كل شيء بعد ذلك.",
  "Choose a CV": "اختر سيرة ذاتية",
  "PDF or Word, or drop it here.": "ملف PDF أو Word، أو اسحبه إلى هنا.",
  "The profile will be filled in from this CV.": "ستُملأ بيانات الملف من هذه السيرة الذاتية.",
  "Full name": "الاسم الكامل", "Optional with a CV": "اختياري مع السيرة الذاتية", "Create Profile": "إنشاء الملف",
  "Choose a CV or type a name.": "اختر سيرة ذاتية أو اكتب اسماً.", "Creating…": "جارٍ الإنشاء…", "Reading the CV…": "جارٍ قراءة السيرة الذاتية…",
  "Profile Created": "تم إنشاء الملف", "Profile Deleted": "تم حذف الملف", "CV Imported": "تم استيراد السيرة الذاتية",
  "That file is larger than 8 MB.": "حجم الملف أكبر من 8 ميغابايت.", "Choose a PDF or Word (.docx) file.": "اختر ملف PDF أو Word ‏(.docx).",
  "The file couldn’t be read.": "تعذّرت قراءة الملف.",
  "Delete {name}’s profile?": "حذف ملف {name}؟", "Delete": "حذف", "Delete Profile": "حذف الملف",
  "The profile moves to the candidates/_deleted folder, so it can be restored by hand. Jobs and CVs already found stay on this computer.":
    "يُنقل الملف إلى مجلد candidates/_deleted، ويمكن استعادته يدوياً. وتبقى الوظائف والسير الذاتية التي وُجدت على هذا الجهاز.",

  // profile
  "Saved automatically as you type": "يُحفظ تلقائياً أثناء الكتابة", "Saving…": "جارٍ الحفظ…",
  "Add {list} to start searching": "أضف {list} لبدء البحث", "a name": "الاسم", "job titles": "المسميات الوظيفية", "CV details": "بيانات السيرة الذاتية",
  "Ready to search": "جاهز للبحث", "Add a headline below": "أضف عنواناً مهنياً بالأسفل", "Import CV": "استيراد سيرة ذاتية", "Preview CV": "معاينة السيرة الذاتية",
  "Filled in from the CV": "مُلئ من السيرة الذاتية",
  "Send matches to": "أرسل الوظائف المطابقة إلى",
  "After each search, the best matches arrive here in one email, with their CVs.": "بعد كل بحث تصل أفضل الوظائف المطابقة إلى هنا في رسالة واحدة مع سيرها الذاتية.",
  "PDF": "PDF", "Email Me": "أرسلها لبريدي", "Sending…": "جارٍ الإرسال…", "Sent to {to}": "أُرسلت إلى {to}",
  "Select the script and copy it by hand.": "حدّد النص وانسخه يدوياً.", "Email is ready": "البريد جاهز",
  "Not set up yet": "لم يُعدّ بعد", "Open": "افتح", "Deploy": "النشر", "Paste the link": "الصق الرابط", "Copy": "نسخ",
  "Save and Send Test": "حفظ وإرسال رسالة تجريبية", "Test Email Sent": "أُرسلت الرسالة التجريبية",
  "Free: the app sends from your own Gmail through a small Google script in your account. Set it up once, in about three minutes.":
    "مجاناً: يرسل التطبيق من بريدك في Gmail عبر نص صغير من Google في حسابك. أعدّه مرة واحدة في نحو ثلاث دقائق.",
  "A new project opens. Delete what is in it, paste this, and press Save.": "يُفتح مشروع جديد. احذف ما فيه، والصق هذا، ثم اضغط حفظ.",
  "Deploy → New deployment → Select type: Web app. Execute as: Me. Who has access: Anyone. Press Deploy, then Authorize access, choose your Google account, Advanced, Go to the project, Allow.":
    "Deploy ← New deployment ← اختر النوع Web app. ثم Execute as: Me و Who has access: Anyone. اضغط Deploy ثم Authorize access، واختر حسابك، ثم Advanced، ثم Go to the project، ثم Allow.",
  "Copy the Web app URL Google shows, paste it here with your email, and send a test.": "انسخ رابط Web app الذي يظهره Google، والصقه هنا مع بريدك، وأرسل رسالة تجريبية.",
  "Add an email for matches in the Profile first.": "أضف بريداً للوظائف المطابقة في الملف أولاً.",
  "Email isn't set up yet. Open Settings, then Email, and follow the three steps.": "لم يُعدّ البريد بعد. افتح الإعدادات ثم البريد الإلكتروني واتبع الخطوات الثلاث.",
  "Free, with a Resend account: 100 emails a day. Set it up once.": "مجاناً عبر حساب في Resend: ‏100 رسالة يومياً. أعدّه مرة واحدة.",
  "Sign up free at": "سجّل مجاناً في", "Create a key": "أنشئ مفتاحاً", "Paste it here": "الصقه هنا",
  "Use the email you want the jobs sent to. Resend sends only to that address.": "استخدم البريد الذي تريد استلام الوظائف عليه، فـResend يرسل إليه فقط.",
  "In Resend, open API Keys, press Create API Key, and copy it (it starts with re_).": "في Resend افتح API Keys واضغط Create API Key ثم انسخه (يبدأ بـ re_).",
  "Paste the key with your email and send a test. Then put the same email in the Profile under Send matches to.":
    "الصق المفتاح مع بريدك وأرسل رسالة تجريبية، ثم ضع البريد نفسه في الملف في خانة «أرسل الوظائف المطابقة إلى».",
  "Key saved. Paste a new one to replace it": "المفتاح محفوظ. الصق مفتاحاً جديداً لاستبداله",
  "That isn't a Resend key. It starts with re_ - copy it from resend.com, API Keys.": "هذا ليس مفتاح Resend. يبدأ المفتاح بـ re_، انسخه من resend.com ضمن API Keys.",
  "Email isn't set up yet. Open Settings, then Email, and paste your Resend key.": "لم يُعدّ البريد بعد. افتح الإعدادات ثم البريد الإلكتروني والصق مفتاح Resend.",
  "Website": "الموقع الشخصي", "Portfolio or personal site, on the CV.": "معرض الأعمال أو الموقع الشخصي، ويظهر في السيرة الذاتية.",
  "For {name}: after each search, the best matches arrive in one email, each with its CV as PDF and Word.":
    "لـ{name}: بعد كل بحث تصل أفضل الوظائف المطابقة في رسالة واحدة، مع سيرة ذاتية لكل وظيفة بصيغتي PDF وWord.",
  "Only this person’s matches go here.": "تصل إلى هنا وظائف هذا الشخص فقط.",
  "Free at {site}: sign up with the address above, then API Keys, Create API Key.": "مجاناً من {site}: سجّل بالبريد أعلاه، ثم API Keys ثم Create API Key.",
  "Test email": "رسالة تجريبية", "Sends a short email to check that it arrives.": "يرسل رسالة قصيرة للتأكد من وصولها.",
  "Add the address and the key first.": "أضف البريد والمفتاح أولاً.", "Send Test": "إرسال تجربة",
  "Email for {name}": "البريد الإلكتروني لـ{name}", "Matches go to {email}": "تُرسل الوظائف المطابقة إلى {email}",
  "After each search, the best matches arrive in one email, each with its CV as PDF and Word. Free with Resend (100 emails a day).":
    "بعد كل بحث تصل أفضل الوظائف المطابقة في رسالة واحدة، مع سيرة ذاتية لكل وظيفة بصيغتي PDF وWord. مجاناً عبر Resend ‏(100 رسالة يومياً).",
  "With the email the jobs should go to. Resend sends only to that address.": "بالبريد الذي تريد استلام الوظائف عليه، فـResend يرسل إليه فقط.",
  "Paste both here": "الصقهما هنا", "Paste the Resend key too: step 2.": "الصق مفتاح Resend أيضاً: الخطوة 2.", "Emails Off": "أُوقفت الرسائل",
  "Set up email for this person first: Settings, Email.": "أعدّ البريد لهذا الشخص أولاً: الإعدادات، البريد الإلكتروني.",
  "Resend key": "مفتاح Resend", "Saved. Paste a new one to replace it": "محفوظ. الصق مفتاحاً جديداً لاستبداله",
  "This profile sends with its own key.": "هذا الملف يرسل بمفتاحه الخاص.",
  "Sign up free at resend.com with the email above, then paste the key from API Keys.": "سجّل مجاناً في resend.com بالبريد أعلاه، ثم الصق المفتاح من API Keys.",
  "Upload PDF": "رفع ملف PDF", "A PDF or Word file: a CV, or a CV with its discovery record": "ملف PDF أو Word: سيرة ذاتية، أو سيرة ذاتية مع ملف الاكتشاف المهني",
  "Upload their PDF: a CV, or a CV with its discovery record. Everything in it is used for the search.":
    "ارفع ملف PDF الخاص به: سيرة ذاتية، أو سيرة ذاتية مع ملف الاكتشاف المهني. يُستخدم كل ما فيه للبحث.",
  "Choose a PDF": "اختر ملف PDF", "Or a Word file. You can also drop it here.": "أو ملف Word، ويمكنك سحبه إلى هنا.",
  "Start from their PDF, or just their name. The app then finds jobs for them and writes a CV for each one.":
    "ابدأ بملف PDF الخاص به أو باسمه فقط. يبحث التطبيق بعدها عن وظائف له ويكتب سيرة ذاتية لكل وظيفة.",
  "From a PDF or a name": "من ملف PDF أو اسم",
  "Filled in from the questionnaire": "مُلئ من الاستبيان", "Filled in from the discovery record": "مُلئ من ملف الاكتشاف المهني",
  "Filled in from the CV and the discovery record": "مُلئ من السيرة الذاتية وملف الاكتشاف المهني", "Imported": "تم الاستيراد",
  "No name was found in the discovery record. Type the person's full name, then create the profile.":
    "لم يُعثر على اسم في ملف الاكتشاف المهني. اكتب الاسم الكامل ثم أنشئ الملف.", "Questionnaire": "الاستبيان", "Import": "استيراد",
  "The questionnaire, filled in with this profile, to send for checking and completing": "الاستبيان مملوءاً ببيانات هذا الملف، لإرساله للمراجعة والإكمال",
  "A filled-in questionnaire, a CV, or a CV with its discovery record": "استبيان بعد تعبئته، أو سيرة ذاتية، أو سيرة ذاتية مع ملف الاكتشاف المهني", "Reading…": "جارٍ القراءة…",
  "Answers Imported": "تم استيراد الإجابات",
  "Send the questionnaire, then add the filled-in file here. A CV or just a name works too, and everything can be changed afterwards.":
    "أرسل الاستبيان، ثم أضف المستند هنا بعد تعبئته. ويمكن البدء أيضاً بسيرة ذاتية أو باسم فقط، وتعديل كل شيء بعد ذلك.",
  "Download the Questionnaire": "تنزيل الاستبيان", "PDF · English and Arabic": "PDF · بالعربية والإنجليزية",
  "Choose the filled-in questionnaire": "اختر الاستبيان بعد تعبئته",
  "Or a CV, with or without its discovery record. PDF or Word, or drop it here.":
    "أو سيرة ذاتية، مع ملف الاكتشاف المهني أو بدونه. بصيغة PDF أو Word، أو اسحبه إلى هنا.",
  "Optional with a file": "اختياري مع المستند", "The profile will be filled in from this file.": "ستُملأ البيانات من هذا المستند.",
  "Choose a file or type a name.": "اختر مستنداً أو اكتب اسماً.",
  "Nationality": "الجنسية", "e.g. Saudi": "مثلاً: سعودي",
  "Jobs open only to other nationalities are skipped.": "تُستبعد الوظائف المخصصة لجنسيات أخرى فقط.",
  "Your field": "مجالك", "Add an industry, speciality or tool": "أضف قطاعاً أو تخصصاً أو أداة",
  "Jobs whose posting mentions these score higher.": "ترتفع درجة الوظيفة التي يذكر إعلانها هذه الكلمات.",
  "Skip companies": "تجاهل الشركات", "Add a company": "أضف شركة",
  "Work Preferences": "تفضيلات العمل", "Years of experience": "سنوات الخبرة", "e.g. 9": "مثلاً: 9",
  "Work arrangement": "نمط العمل", "Job type": "نوع الوظيفة", "On-site": "حضوري", "Hybrid": "هجين", "Remote": "عن بُعد",
  "Full-time": "دوام كامل", "Part-time": "دوام جزئي", "Contract": "عقد مؤقت",
  "Relocation": "الانتقال", "e.g. Jeddah or Dubai": "مثلاً: جدة أو دبي", "Notice period": "مدة الإشعار",
  "e.g. One month": "مثلاً: شهر واحد", "Expected salary": "الراتب المتوقع", "e.g. 30,000 SAR a month": "مثلاً: 30,000 ريال شهرياً",
  "Residency or visa": "الإقامة أو التأشيرة", "e.g. Transferable iqama": "مثلاً: إقامة قابلة للنقل", "Anything else": "أي شيء آخر",
  "Must-haves, deal-breakers, companies they’d love to join": "الشروط الأساسية، وما لا يقبله، والشركات التي يتمنى العمل فيها",
  "For applying by hand, and for ChatGPT when it’s on. Never written into a CV.":
    "للتقديم يدوياً، ولـ ChatGPT عند تشغيله. ولا تُكتب في السيرة الذاتية أبداً.",
  "{list}. Read each part, and fix anything the CV didn’t say clearly.": "{list}. راجع كل جزء، وصحّح ما لم تذكره السيرة الذاتية بوضوح.",
  "Personal Details": "البيانات الشخصية", "Headline": "العنوان المهني", "City": "المدينة", "Email": "البريد الإلكتروني", "Phone": "الهاتف", "LinkedIn": "LinkedIn",
  "First and last name": "الاسم الأول والأخير", "e.g. Senior Financial Analyst": "مثلاً: محلل مالي أول", "e.g. Riyadh": "مثلاً: الرياض",
  "Contact details appear on the CV only. They’re never sent to ChatGPT.": "تظهر بيانات التواصل في السيرة الذاتية فقط، ولا تُرسل إلى ChatGPT أبداً.",
  "Job titles to search": "المسميات الوظيفية للبحث", "Each search looks for these titles. Press Enter after each one.":
    "يبحث كل بحث عن هذه المسميات. اضغط Enter بعد كل مسمّى.",
  "Add a job title": "أضف مسمّى وظيفياً", "Country": "الدولة",
  "Skip titles with": "تجاهل المسميات التي فيها", "Jobs whose title has one of these words are dropped before scoring.":
    "تُستبعد الوظائف التي يحتوي مسمّاها على إحدى هذه الكلمات قبل التقييم.",
  "Add a word, e.g. Sales": "أضف كلمة، مثلاً: Sales", "{searches} per site, with up to 4 titles in each.": "{searches} في كل موقع، بحد أقصى 4 مسميات في كل منها.",
  "Entry level": "مبتدئ", "Associate": "مساعد", "Mid–Senior": "متوسط إلى أول", "Director": "مدير", "Executive": "تنفيذي",
  "Needed": "مطلوب", "Remove {x}": "إزالة {x}", "Remove": "إزالة",
  "Summary": "الملخص", "Two or three sentences on experience and strengths. A blank line starts a new paragraph.":
    "جملتان أو ثلاث عن الخبرة ونقاط القوة. السطر الفارغ يبدأ فقرة جديدة.",
  "Key Achievements": "أبرز الإنجازات", "One achievement per line": "إنجاز واحد في كل سطر",
  "Experience": "الخبرات", "Add Role": "إضافة وظيفة", "Job title": "المسمّى الوظيفي", "Company": "الشركة", "e.g. Jan 2020 – Present": "مثلاً: Jan 2020 – Present",
  "One line about the role (optional)": "سطر عن الوظيفة (اختياري)", "What you did and achieved, one point per line": "ما قمت به وما حققته، نقطة في كل سطر",
  "Remove this role": "إزالة هذه الوظيفة",
  "Skills": "المهارات", "Add a skill": "أضف مهارة",
  "The first eight are the CV’s core competencies. Free scoring also uses them to recognise jobs in this field.":
    "أول ثماني مهارات هي الكفاءات الأساسية في السيرة الذاتية، ويستخدمها التقييم المجاني أيضاً للتعرّف على وظائف هذا المجال.",
  "Education": "التعليم", "Add Education": "إضافة مؤهل", "Degree or qualification": "الشهادة أو المؤهل", "University or school": "الجامعة أو المدرسة", "Year": "السنة",
  "More for the CV": "المزيد للسيرة الذاتية", "Certifications": "الشهادات المهنية", "Languages": "اللغات", "Training": "التدريب", "Awards": "الجوائز",
  "One per line": "واحد في كل سطر", "Job titles": "المسميات الوظيفية", "Name": "الاسم",
  "Notes for ChatGPT": "ملاحظات لـ ChatGPT", "e.g. Egyptian, living in Riyadh. Won’t relocate. Available in one month.":
    "مثلاً: مصري مقيم في الرياض، لا يرغب في الانتقال، ومتاح خلال شهر.",
  "Read only when ChatGPT is on, to judge each job. Never written into a CV.": "يقرؤها ChatGPT فقط عند تشغيله لتقييم كل وظيفة، ولا تُكتب في السيرة الذاتية أبداً.",
  "The tracks are drafts until the client approves them.": "المسارات مسودّات حتى يوافق عليها العميل.",
  "Open Profile": "فتح الملف", "Open Settings": "فتح الإعدادات", "job titles to search": "المسميات الوظيفية للبحث",
  "Add the job titles to search in the profile, then run the first search.": "أضف المسميات الوظيفية للبحث في الملف، ثم ابدأ أول بحث.",
  "Finish Settings, then run the first search.": "أكمل الإعدادات، ثم ابدأ أول بحث.",

  // searching
  "Find New Jobs": "ابحث عن وظائف جديدة", "Searching…": "جارٍ البحث…",
  "Looks for jobs posted since the last search and adds the new ones to the list": "يبحث عن الوظائف المنشورة منذ آخر بحث ويضيف الجديد منها إلى القائمة",
  "{sites} in {country} · {titles} · posted in the last {period}": "{sites} في {country} · {titles} · المنشورة خلال آخر {period}",
  "Finish Settings before searching.": "أكمل الإعدادات قبل البحث.", "Add the job titles to search in the profile first.": "أضف المسميات الوظيفية للبحث في الملف أولاً.",
  "Finding jobs for {name}": "جارٍ البحث عن وظائف لـ{name}", "This takes one to three minutes. You can keep using the app.": "يستغرق ذلك من دقيقة إلى ثلاث دقائق، ويمكنك متابعة استخدام التطبيق.",
  "Find jobs for {name}": "ابحث عن وظائف لـ{name}", "Add the job titles to search in the profile, then search.": "أضف المسميات الوظيفية للبحث في الملف، ثم ابدأ البحث.",
  "Finish Settings, then search.": "أكمل الإعدادات، ثم ابدأ البحث.", "Try a demo search for {name}": "جرّب بحثاً تجريبياً لـ{name}",
  "Sample jobs and simulated scoring, so you can see how it all works.": "وظائف تجريبية وتقييم محاكى، لترى كيف يعمل كل شيء.",
  "Edit Profile": "تعديل الملف",
  "New jobs are scored against {name}’s profile, and each good match gets its own CV. Every later search adds only jobs that are new.":
    "تُقيَّم الوظائف الجديدة مقارنةً بملف {name}، وتحصل كل وظيفة مناسبة على سيرة ذاتية خاصة بها. وكل بحث لاحق يضيف الوظائف الجديدة فقط.",
  "Each search looks for jobs posted since the last one, skips any already in the list, and adds only the new ones.":
    "يبحث كل بحث عن الوظائف المنشورة منذ البحث السابق، ويتجاوز الموجود في القائمة، ويضيف الجديد فقط.",
  "{jobs} added": "أُضيفت {jobs}", "No new jobs this time": "لا وظائف جديدة هذه المرة",
  "Delete Job": "حذف الوظيفة", "Job deleted": "حُذفت الوظيفة", "Undo": "تراجع",
  "Clear {name}’s jobs?": "مسح وظائف {name}؟", "Clear Jobs": "مسح الوظائف", "Clear Jobs…": "مسح الوظائف…", "Jobs Cleared": "تم مسح الوظائف",
  "Every job, CV and Applied mark in the list is removed, and the next search starts fresh. A copy is kept in the backups folder.":
    "تُحذف كل الوظائف والسير الذاتية وعلامات التقديم من القائمة، ويبدأ البحث التالي من جديد. وتُحفظ نسخة في مجلد backups.",
  "Delete Profile…": "حذف الملف…", "Add a headline": "أضف عنواناً مهنياً", "What each search looks for.": "ما يبحث عنه كل بحث.",
  "Add a job title, then press Enter": "أضف مسمّى وظيفياً ثم اضغط Enter", "One per line.": "واحد في كل سطر.",
  "Wait for the running search to finish first.": "انتظر حتى ينتهي البحث الجاري أولاً.",

  // messages from the server
  "No name was found in the CV. Type the person's full name, then create the profile.":
    "لم يُعثر على اسم في السيرة الذاتية. اكتب الاسم الكامل ثم أنشئ الملف.",
  "No name was found in the questionnaire. Type the person's full name, then create the profile.":
    "لم يُعثر على اسم في الاستبيان. اكتب الاسم الكامل ثم أنشئ الملف.",
  "This questionnaire was printed to PDF, which removes the answers. Open the one that was sent, fill it in, and use Save instead of Print.":
    "طُبع هذا الاستبيان بصيغة PDF، وهذا يحذف الإجابات. افتح النسخة المرسلة واملأها، ثم استخدم «حفظ» بدلاً من «طباعة».",
  "Add the person's full name.": "أضف الاسم الكامل.", "The email address doesn't look right.": "يبدو أن البريد الإلكتروني غير صحيح.",
  "The LinkedIn address doesn't look right.": "يبدو أن رابط LinkedIn غير صحيح.",
  "No text was found in this file. If it's a scanned image, use the Word or text version.":
    "لم يُعثر على نص في هذا الملف. إن كان صورة ممسوحة ضوئياً، فاستخدم نسخة Word أو النص.",
  "This PDF couldn't be opened. Try saving it again, or use the Word file.": "تعذّر فتح ملف PDF هذا. احفظه من جديد أو استخدم ملف Word.",
  "This Word file couldn't be opened.": "تعذّر فتح ملف Word هذا.", "That file is larger than 8 MB": "حجم الملف أكبر من 8 ميغابايت",
  "The file didn't arrive in one piece. Try again.": "لم يصل الملف كاملاً. حاول مرة أخرى.",
  "Only profiles made in the app can be deleted here.": "يمكن هنا حذف الملفات التي أُنشئت من التطبيق فقط.",
  "Searching {sites}…": "جارٍ البحث في {sites}…", "{postings} found": "تم العثور على {postings}",
  "{jobs} fit the profile": "{jobs} تناسب الملف", "Scoring {jobs}…": "جارٍ تقييم {jobs}…",
  "Writing {cvs}…": "جارٍ كتابة {cvs}…", "Saving the results…": "جارٍ حفظ النتائج…",
  "{n} days ago": "منذ {n} أيام", "Site": "المنصة", "Level": "المستوى", "Senior": "أول", "Junior": "مبتدئ",
  "Entry or specialist level": "مستوى مبتدئ أو اختصاصي","New from the latest search": "جديد من آخر بحث",
  "Apply first.": "تقدّم لها أولاً.", "Worth a careful look.": "تستحق نظرة متأنية.",
  "Partly fits. Read it before applying.": "تناسب جزئياً. اقرأها قبل التقديم.",
  "The title matches “{terms}”.": "المسمّى يطابق «{terms}».",
  "The title is close to the profile’s job titles.": "المسمّى قريب من المسميات الوظيفية في الملف.",
  "The title isn’t one of the profile’s job titles.": "المسمّى ليس من المسميات الوظيفية في الملف.",
  "{level} is a level the profile targets.": "مستوى {level} من المستويات التي يستهدفها الملف.",
  "{level} is one step from the profile’s levels.": "مستوى {level} أعلى أو أقل بدرجة واحدة من مستويات الملف.",
  "The level is junior for this profile.": "المستوى أقل من مستوى هذا الملف.",
  "The posting asks for {terms}.": "يطلب الإعلان {terms}.",
  "The posting doesn’t mention the profile’s skills.": "لا يذكر الإعلان مهارات الملف.",
  "The site didn’t share the description, so only the title was judged.": "لم يشارك الموقع وصف الوظيفة، لذلك قُيّم المسمّى فقط.",
  "Open only to a specific nationality, so it scores 0.": "مخصصة لجنسية محددة فقط، لذلك درجتها 0.",
  "Read the full posting": "قراءة الإعلان كاملاً", "Applied. Click to clear the mark": "تم التقديم. اضغط لإزالة العلامة",
  "Reading the posting from LinkedIn…": "جارٍ قراءة الإعلان من LinkedIn…",
  "{site} didn’t share the description. Open the posting to read it.": "لم يشارك {site} وصف الوظيفة. افتح الإعلان لقراءته.",
  "The profile and its jobs leave the app. A backup copy is kept on this computer.": "يُزال الملف ووظائفه من التطبيق، مع الاحتفاظ بنسخة احتياطية على هذا الجهاز.",
  "Add the first person": "أضف أول شخص",
  "Start from the questionnaire they fill in, their CV, or just their name. The app then finds jobs for them and writes a CV for each one.":
    "ابدأ بالاستبيان الذي يملؤه، أو بسيرته الذاتية، أو باسمه فقط. يبحث التطبيق بعدها عن وظائف له ويكتب سيرة ذاتية لكل وظيفة.",
};

/* Arabic plural forms: [one, two, 3-10, 11+]. */
window.AR_COUNT = {
  job: ["وظيفة واحدة", "وظيفتان", "وظائف", "وظيفة"],
  match: ["وظيفة مطابقة واحدة", "وظيفتان مطابقتان", "وظائف مطابقة", "وظيفة مطابقة"],
  keyword: ["كلمة مفتاحية واحدة", "كلمتان مفتاحيتان", "كلمات مفتاحية", "كلمة مفتاحية"],
  search: ["بحث واحد", "بحثان", "عمليات بحث", "عملية بحث"],
  title: ["مسمّى وظيفي واحد", "مسمّيان وظيفيان", "مسميات وظيفية", "مسمّى وظيفياً"],
  newjob: ["وظيفة جديدة واحدة", "وظيفتان جديدتان", "وظائف جديدة", "وظيفة جديدة"],
  posting: ["إعلان واحد", "إعلانان", "إعلانات", "إعلاناً"],
  cv: ["سيرة ذاتية واحدة", "سيرتان ذاتيتان", "سير ذاتية", "سيرة ذاتية"],
};

/* Client Setup rows come from the server in English; these are their Arabic versions, by row id. */
window.AR_SETUP = {
  groups: { scoring: "التقييم والسير الذاتية", email: "ملخص البريد",
            recipients: "مستلمو البريد", candidate: "الموافقات" },
  items: {
    ai: { title: "استخدام ChatGPT",
      why: "مجاني عند الإيقاف. وعند التشغيل يقيّم ChatGPT الوظائف ويكتب السير الذاتية، برسوم لكل بحث." },
    openai: { title: "مفتاح OpenAI (ChatGPT)", why: "يقيّم الوظائف ويكتب السير الذاتية.",
      where: "platform.openai.com/api-keys (مفتاح API، وليس اشتراك ChatGPT Plus)" },
    credit: { title: "إضافة رصيد لحساب OpenAI", why: "يُدفع حسب الاستخدام، منفصلاً عن ChatGPT Plus. تستخدم عمليات البحث {model}.",
      where: "platform.openai.com ← Settings ← Billing" },
    domain: { title: "توثيق نطاق المُرسِل (SPF وDKIM)", why: "بدونه يصل الملخص إلى البريد المزعج أو يُرفض." },
    brevo: { title: "مفتاح Brevo", why: "يرسل بريد الملخص اليومي مع السير الذاتية مرفقة." },
    sender: { title: "عنوان المُرسِل الموثّق", why: "العنوان الذي يُرسل منه الملخص، ويجب توثيقه في Brevo." },
    recipient: { title: "البريد الإلكتروني للملخص اليومي", why: "العنوان الذي يُرسل إليه ملخص {name} وسيره الذاتية، ولا يستلمها غيره." },
    cc: { title: "عناوين النسخة", why: "أي شخص آخر يجب أن يستلم الملخص (افصل بينها بفواصل)." },
    sources: { title: "مواقع الوظائف التي يُبحث فيها", why: "LinkedIn وIndeed مفعّلان، ويمكن إضافة Bayt أيضاً، والبحث فيها كلها مجاني." },
    go_ahead: { title: "الموافقة على تقييم الوظائف لـ{name}", why: "يطلب سجل المرحلة الأولى إذناً صريحاً قبل تقييم أي وظيفة." },
    tracks: { title: "اعتماد المسارات المهنية الخمسة",
      why: "مستمدة من الأدوار المستهدفة: قيادة المنتجات، ومنتجات الذكاء الاصطناعي، والتقنية المالية والبيانات المالية، والتسليم والبرامج والمشاريع، والتجارة الإلكترونية." },
    keywords: { title: "اعتماد الكلمات المفتاحية وفلتر المسميات الوظيفية", why: "تحدد الإعلانات التي تُجمع، وتلك التي تُستبعد قبل التقييم." },
    degree: { title: "الاسم الإنجليزي الدقيق لشهادة البكالوريوس",
      why: "تذكر السيرة الذاتية حالياً «Bachelor's Degree in Translation — Cairo University»، ويشير السجل إلى أن الصياغة غير مؤكدة." },
    certificates: { title: "الأسماء والتواريخ الدقيقة للشهادات",
      why: "اثنتا عشرة شهادة من IBM وGoogle وCoursera مذكورة بأسماء مختصرة، ويطلب السجل أسماءها وتواريخها الحرفية." },
  },
};
