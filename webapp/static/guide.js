"use strict";
/* "How It Works" - the client's guide, in English and Arabic: only what helps someone use the app.
   guideContent(lang, ctx) -> { title, lede, sections: [{ id, icon, color, title, html }] }
   ctx: { name, sites: ["LinkedIn", ...], keywords, searches, location, t: { strong, good, moderate } }
   Every number and name comes from ctx, so the guide always describes what the app really does. */

(function () {
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const p = (t) => `<p>${t}</p>`;
  const list = (items) => `<ul class="g-list">${items.map((i) => `<li>${i}</li>`).join("")}</ul>`;
  const steps = (items) => `<ol class="g-steps">${items.map(([h, t], n) =>
    `<li><span class="g-n">${n + 1}</span><div><b>${h}</b><p>${t}</p></div></li>`).join("")}</ol>`;
  const table = (head, rows, spec) => `<div class="g-table" style="--spec:${spec}">
    <div class="g-tr g-th">${head.map((h) => `<span>${h}</span>`).join("")}</div>
    ${rows.map((r) => `<div class="g-tr">${r.map((c) => `<span>${c}</span>`).join("")}</div>`).join("")}</div>`;
  const qa = (items) => items.map(([q, a]) => `<details class="g-qa"><summary><span>${q}</span></summary><p>${a}</p></details>`).join("");
  const b = (t) => `<bdi>${t}</bdi>`;          // English names inside Arabic text keep their own direction
  const v = (name, cls) => `<span class="g-v v-${cls}">${name}</span>`;

  function en(c) {
    const name = esc(c.name), loc = esc(c.location), t = c.t;
    const sites = c.sites.map(esc).join(", ").replace(/, ([^,]*)$/, " and $1");
    return {
      title: "How It Works",
      lede: "What the app does, and how to use it.",
      toc: "On this page",
      sections: [
        { id: "overview", icon: "apps", color: "blue", title: "What the app does", html:
          p(`It finds new jobs that suit ${name}, scores how well each one fits, and makes a CV for each job. You review the matches and apply in a couple of clicks.`) +
          p("It never applies or sends anything for you. Every application goes out from you.") },
        { id: "flow", icon: "play", color: "indigo", title: "What happens in a search", html:
          steps([
            ["Search", `Reads new postings from ${sites} for the job titles in the profile, posted within the look-back set in Settings.`],
            ["Filter", `Removes duplicates, jobs already seen, older postings, unrelated titles and jobs outside ${loc}.`],
            ["Score", "Gives each job a fit score from 0 to 100."],
            ["CV", "Every job has a “Download CV” button that makes a CV for that job."],
            ["You apply", "Open the posting, attach the CV and apply. Then press “Mark as Applied”."],
          ]) },
        { id: "scoring", icon: "gauge", color: "green", title: "What the scores mean", html:
          table(["Verdict", "Score", "What it means"], [
            [v("Strong", "strong"), `${t.strong}+`, "Apply first."],
            [v("Good", "good"), `${t.good}–${t.strong - 1}`, "Worth a careful look."],
            [v("Moderate", "moderate"), `${t.moderate}–${t.good - 1}`, "Partly fits. Listed under All."],
            [v("Weak", "weak"), `below ${t.moderate}`, "Not a fit. Listed under All."],
          ], "1fr .8fr 2.4fr") +
          list([
            "The score shows how closely the posting matches the profile’s job titles, skills and level.",
            "A posting open only to a specific nationality scores 0.",
          ]) },
        { id: "cvs", icon: "doc", color: "orange", title: "The CVs", html:
          p("<b>Download CV</b> makes a Word CV for that job: the job’s title as the headline, the matching skills and achievements first, and a summary that ties the experience to the role.") +
          p("It uses only the details in the profile, so nothing is made up. You can edit it in Word before sending.") },
        { id: "faq", icon: "question", color: "pink", title: "Questions", html:
          qa([
            ["Does a search start over each time?", "No. <b>Find New Jobs</b> only adds jobs that are new since the last search. Jobs already in the list, or deleted from it, never come back. To really start over, use <b>Clear Jobs…</b> in the profile."],
            ["How long does a search take?", "About 1 to 3 minutes. Once a day is enough."],
            ["Why do I see no jobs, or no matches?", `Either no search has run yet, or nothing scored ${t.good} or more. Choose <b>All</b> to see every job, or press <b>Find New Jobs</b>. Keep the job titles in the profile close to the roles you really want.`],
            ["How do I remove a job I don’t want?", "Press the trash button on the job. <b>Undo</b> appears for a few seconds in case it was a mistake."],
            ["Why did a good-looking job score low?", "Usually because the posting doesn’t use the profile’s terms, or the title is junior. <b>Why It Fits</b> shows what matched."],
            ["Does it cost anything?", "No, it is free. ChatGPT in Settings is an optional paid extra."],
            ["Can it apply for me?", "No, by design. It prepares everything; you send the application."],
          ]) },
      ],
    };
  }

  function ar(c) {
    const name = esc(c.name), loc = esc(c.location), t = c.t;
    const sites = c.sites.map((s) => b(esc(s))).join("، ").replace(/، ([^،]*)$/, " و$1");
    return {
      title: "كيف يعمل التطبيق",
      lede: "ماذا يفعل التطبيق، وكيف تستخدمه.",
      toc: "في هذه الصفحة",
      sections: [
        { id: "overview", icon: "apps", color: "blue", title: "ماذا يفعل التطبيق", html:
          p(`يجد وظائف جديدة تناسب ${b(name)}، ويقيّم مدى ملاءمة كل وظيفة، وينشئ سيرة ذاتية لكل وظيفة. تراجع الوظائف المطابقة وتتقدّم بنقرتين.`) +
          p("لا يتقدّم ولا يرسل أي شيء نيابةً عنك. كل طلب يخرج منك أنت.") },
        { id: "flow", icon: "play", color: "indigo", title: "ماذا يحدث في عملية البحث", html:
          steps([
            ["البحث", `يقرأ الإعلانات الجديدة من ${sites} للمسميات الوظيفية في الملف، المنشورة خلال المدة المحددة في الإعدادات.`],
            ["التصفية", `يستبعد المكرر، وما سبق ظهوره، والإعلانات الأقدم، والمسميات البعيدة، والوظائف خارج ${b(loc)}.`],
            ["التقييم", "يعطي كل وظيفة درجة توافق من 0 إلى 100."],
            ["السيرة الذاتية", "لكل وظيفة زر «تنزيل السيرة الذاتية» الذي ينشئ سيرة ذاتية لهذه الوظيفة."],
            ["التقديم", "افتح الإعلان، وأرفق السيرة الذاتية، وقدّم. ثم اضغط «وضع علامة التقديم»."],
          ]) },
        { id: "scoring", icon: "gauge", color: "green", title: "ماذا تعني الدرجات", html:
          table(["التصنيف", "الدرجة", "المعنى"], [
            [v("قوي", "strong"), `${t.strong} فأكثر`, "تقدّم لها أولاً."],
            [v("جيد", "good"), `${t.good}–${t.strong - 1}`, "تستحق نظرة متأنية."],
            [v("متوسط", "moderate"), `${t.moderate}–${t.good - 1}`, "تناسب جزئياً، وتظهر ضمن «الكل»."],
            [v("ضعيف", "weak"), `أقل من ${t.moderate}`, "لا تناسب، وتظهر ضمن «الكل»."],
          ], "1.2fr .8fr 2.4fr") +
          list([
            "تعكس الدرجة مدى تطابق الإعلان مع المسميات الوظيفية والمهارات والمستوى في الملف.",
            "الإعلان المخصص لجنسية محددة فقط يحصل على 0.",
          ]) },
        { id: "cvs", icon: "doc", color: "orange", title: "السير الذاتية", html:
          p(`«تنزيل السيرة الذاتية» ينشئ ملف ${b("Word")} لهذه الوظيفة: مسمّاها عنواناً، والمهارات والإنجازات المطابقة أولاً، وملخصاً يربط الخبرة بالدور.`) +
          p(`يستخدم فقط البيانات الموجودة في الملف، فلا شيء مختلَق. ويمكنك تعديله في ${b("Word")} قبل الإرسال.`) },
        { id: "faq", icon: "question", color: "pink", title: "أسئلة شائعة", html:
          qa([
            ["هل يبدأ البحث من جديد في كل مرة؟", "لا. زر «ابحث عن وظائف جديدة» يضيف فقط الوظائف الجديدة منذ البحث السابق. والوظائف الموجودة في القائمة أو المحذوفة منها لا تعود. وللبدء فعلاً من الصفر استخدم «مسح الوظائف…» في الملف."],
            ["كم يستغرق البحث؟", "من دقيقة إلى ثلاث دقائق تقريباً. ومرة واحدة يومياً تكفي."],
            ["لماذا لا تظهر وظائف، أو لا توجد وظائف مطابقة؟", `إما أنه لم يُجرَ أي بحث بعد، أو لم تحصل أي وظيفة على ${t.good} أو أكثر. اختر «الكل» لرؤية كل الوظائف، أو اضغط «ابحث عن وظائف جديدة». واجعل المسميات الوظيفية في الملف قريبة من الأدوار التي تريدها فعلاً.`],
            ["كيف أحذف وظيفة لا أريدها؟", "اضغط زر سلة المهملات في الوظيفة. ويظهر زر «تراجع» لبضع ثوانٍ تحسّباً للخطأ."],
            ["لماذا حصلت وظيفة تبدو مناسبة على درجة منخفضة؟", "غالباً لأن الإعلان لا يستخدم مصطلحات الملف، أو لأن المسمّى أدنى من المستوى. يوضّح قسم «لماذا تناسب» ما تمت مطابقته."],
            ["هل يكلّف أي شيء؟", `لا، فهو مجاني. و${b("ChatGPT")} في الإعدادات إضافة اختيارية مدفوعة.`],
            ["هل يمكنه التقديم نيابةً عني؟", "لا، وهذا مقصود. فهو يجهّز كل شيء، وأنت من يرسل الطلب."],
          ]) },
      ],
    };
  }

  window.guideContent = (lang, ctx) => (lang === "ar" ? ar(ctx) : en(ctx));
})();
