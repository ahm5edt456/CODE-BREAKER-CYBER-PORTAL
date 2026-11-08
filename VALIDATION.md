# التحقق من التحديث

اجتازت النسخة اختبارات آلية على Linux باستخدام SDL dummy:

- التحكم بالقائمة الرئيسية والإعدادات بالأسهم وEnter وTab وShift+Tab.
- الإعدادات محصورة بنوع المشكلة (Debugging أو Complete Code) والصوت.
- إنشاء مهمتين من مستويين مختلفين: سهل ثم متوسط؛ دون اختيار يدوي للصعوبة.
- تنفيذ الحل المرجعي وفتح البوابات في نوعي التحدي باستخدام Python وC++.
- Run لا يخصم قلباً، وحل المهمتين ينهي الجولة.
- الفوز والخسارة ينتقلان إلى شاشة إدخال الاسم، ولا يحفظان اسماً افتراضياً.
- حفظ الاسم والنتيجة، رفض الاسم الفارغ، وحد طول الاسم وتعديل النص.
- عدم تكرار النتيجة عند الضغط مجدداً، وإعادة محاولة الحفظ بعد فشل الكتابة.
- تخطي الحفظ لا يكتب نتيجة مجهولة.
- استمرار جمع الطاقة والاندفاعة، وأخطاء التنفيذ والمهلة الزمنية.

تمت مراجعة صور القائمة والإعدادات وشاشة الاسم. الاختبارات تحفظ النتائج في مجلد مؤقت، ولا تتضمن الحزمة أية نتائج اختبار محفوظة.

Java متاحة في التنفيذ، لكنها تحتاج إلى اختبار على جهاز فيه JDK. الصوت وملء الشاشة والكيبورد الفعلي وWindows تحتاج تجربة على جهاز العرض.


## واجهة Cyber Portal

اجتازت النسخة اختبارات pygame_gui الفعلية باستخدام pygame-ce 2.5.8 وpygame_gui 0.6.14، بما فيها:

- إنشاء الأزرار كعناصر UIButton وخانة الاسم كعنصر UITextEntryLine.
- تغير الرسوم مع مرور الوقت، والتنقل بالأسهم وفق مواضع العناصر الجديدة.
- تنشيط الأزرار بنقرات mouse down/up، وتغيير الصوت مرة واحدة لكل نقرة.
- الكتابة والتعديل في خانة الاسم، والحفظ عبر Enter دون تكرار النتيجة.
- دخول اللعبة من الواجهة، وحل المهمتين، ثم إدخال الاسم وعرض النتائج.
- اجتياز اختبارات منطق اللعبة السابقة باستخدام المكتبات الجديدة.

تمت مراجعة صور القائمة والإعدادات والاسم وHigh Scores، وفحص صياغة سكربتات Linux. اختبارات الماوس والكيبورد هنا محاكاة عبر SDL dummy؛ جرّب ملء الشاشة والصوت على جهاز الإيفينت. لم تُختبر سكربتات Windows على Windows.

## الحملة وشاشة اللعب الجديدة

نجح test_campaign.py في:

- تشغيل الحلول المرجعية والتأكد من اختلاف الكود المعيب عن الحل، لكل المفاهيم الستة ونوعي التحدّي على Python وC++.
- التنقل الفعلي داخل المتاهة إلى كل بوابة، وحل التحدّيات بالترتيب عبر المراحل الثلاث.
- التأكد من أن حل البوابات لا ينهي المرحلة فوراً، وأن المخرج القديم لا ينهيها، وأن العودة إلى البداية وحدها تنهيها بعد حل البوابات.
- ظهور شاشة انتقال للمراحل، والفوز النهائي وخانة الاسم بعد إكمال المرحلة الثالثة فقط.
- الإيقاف المؤقت وانتهاء الوقت والحفظ النهائي للنتيجة.
- إنشاء واجهة المتاهة والمحرر بأزرار pygame_gui، ومراجعة صور المتاهة والمحرر والعودة والإيقاف والانتقال.

اجتازت اختبارات game وportal السابقة أيضاً. تم اختبار زر PAUSE الفعلي وتجميد العداد. تم الحفاظ على حجم المتاهة 13×9، وأزيل رسم نقاط التوجيه وأثر الحركة من شاشة الحملة.

## محاذاة الأرقام وتناسق الأشكال

تم توسيط الجزء المرئي من الأرقام 1 إلى 6 داخل الدوائر بعد استبعاد المساحات الشفافة للخط، والتحقق من تطابق مركز الرسم مع مركز الدائرة. تستخدم المراحل والبوابات وقائمة المهام نفس نصف القطر وسماكة الحدود والخط. أزيل شريط الباب البارز خلف الدائرة، ووُحّد حجم قطع الطاقة وزوايا البطاقات وإطار تحديد الأزرار. تمت مراجعة صور المرحلة الأولى والثالثة والمحرر وحالة العودة إلى البداية. هذا التحديث بصري فقط.

## توزيع التحدّيات والانتقال التلقائي

استُبدلت آلية العودة إلى البداية بانتقال تلقائي بعد حل آخر تحدٍّ. نجحت اختبارات 100 متاهة مختلفة: التحدّيات خارج زاوية البداية، في مناطق متباعدة، مع قابلية الوصول إليها حسب ترتيب الصعوبة ودون انسداد المسار إلى التحدّي الأول.

اجتاز اختبار الحملة تنقلاً فعلياً بين مواقع الأسئلة وإكمال المراحل الثلاث تلقائياً، بالإضافة إلى نوعي التحدّيات، وتجميد الوقت أثناء الإيقاف، وانتهاء الوقت وحفظ النتيجة النهائية. اختُبرت الحلول المرجعية والنسخ الخاطئة للمفاهيم الستة على Python وC++. كما عُزل مولّد خلفية القائمة عن حالة العشوائية حتى لا يعيد نفس أول متاهة عند كل تشغيل.

تصف فقرات العودة إلى البداية أعلاه سلوك النسخة السابقة؛ السلوك الحالي هو الإكمال والانتقال التلقائي دون عودة أو مخرج.

## الحفظ في Dashboard JSON

اجتاز اختبار الحفظ قراءة وكتابة ملف JSON جديد، والأسماء العربية دون تحويلها إلى رموز Unicode مهروبة، ونقل النتائج القديمة. تم التحقق من بقاء الحفظ السابق عند فشل الاستبدال وعدم ترك ملفات مؤقتة، ومن عدم إعادة استيراد النتائج القديمة بعد إفراغ القائمة يدوياً.

اجتازت اختبارات اللعبة والواجهة الحفظ في المسار الجديد وإعادة المحاولة دون تكرار السجلات. تم إنشاء حملة وحفظ إحصاءاتها ثم تحميلها في كائن لعبة جديد، والتحقق من أن الملف التالف يبقى دون تعديل عند محاولة الحفظ.

## نقاط السرعة ومنع تكرار الأسماء

نجح اختبار مكافآت 0 و10 و30 و50 و80 ثانية، والتحقق من أن الحل الأسرع يحصل على نقاط أكثر وأن النجاح لا يُكافأ مرتين. تم اختبار استمرار العداد عند الرجوع للسؤال، وتوقفه أثناء الإيقاف وتشغيل الكود، وحفظ استعمال التلميح، وتخزين أزمنة الحل ومكافآت السرعة واسترجاعها.

تم اختبار دمج اختلاف حالة الأحرف والمسافات وأحرف Unicode المتوافقة، وتحديث أفضل نتيجة في سجل واحد، وعدم استدعاء الكتابة أصلاً للنتيجة المتكررة الأقل، وتنظيف التكرارات في ملف JSON قديم. تعادل النقاط يُحسم بالدقة ثم الوقت.

## إعادة ضبط النتائج والأسئلة والماوس

في النسخة الحالية أزيل استيراد النتائج القديمة نهائياً. اختُبر حذف dashboard.json أثناء تشغيل اللعبة، ثم حفظ اسم جديد، والتأكد من أن الملف لا يحتوي الأسماء المحذوفة. اختُبرت إعادة فتح High Scores وحذف الملف واللوحة مفتوحة.

اجتاز البنك الجديد اختبارات اختيار ستة أنواع مختلفة من عشرة عبر 100 اختيار عشوائي، مع تدرّجها بين ثلاث درجات. تم تنفيذ الحل الصحيح والكود المعيب لكل الأنواع على Python وC++، واختبار Complete Code فعلياً بكتابة السطر الناقص المختار تلقائياً، لجميع الأنواع العشرة على Python وC++.

تم اختبار النقر الدقيق للمؤشر، والسحب لتحديد النص واستبداله، والنقر المزدوج للكلمات، والنسخ واللصق، والتمرير بالعجلة والشريط، والمسافة البادئة، وحفظ المسودة، وقائمة الزر الأيمن مع إزالة عناصرها عند إغلاقها. اختبارات الماوس آلية باستخدام SDL dummy؛ تبقى تجربة الحافظة والصوت وملء الشاشة على جهاز العرض مطلوبة.

الفقرات السابقة التي تتحدث عن ترحيل النتائج أو تسلسل ثابت لستة أنواع توثّق نسخاً سابقة، ولا تصف السلوك الحالي.


## Protected local Fedora verification — 2026-11-08

Verified on the user's normal Fedora session at **2026-11-08T17:55:48.508044+00:00**
using `bash local.sh verify`. Source: the actual `local-verification.json`, whose
status is `passed` and whose nine language/mode flows all completed.

| Language | Debug | Complete Code | Predict Output |
| --- | --- | --- | --- |
| Python | Passed | Passed | Passed |
| C++ | Passed | Passed | Passed |
| Java | Passed | Passed | Passed |

Each flow used an actual campaign challenge and the game's reference-output,
Run and Submit paths. In Debug and Complete Code, Run produced the required
output without opening the gate or changing lives; Submit opened the gate and
awarded points. Native answers included trailing comments. Predict Output used
reference generation and prediction submission; its Run action retained the
original informational behavior and did not execute player code.

The session retained delegated cgroups, namespace isolation, blocked networking,
restricted mounts, sanitized compiler/runtime environments, syscall filters and
resource/output limits. Bubblewrap's added `PWD` was removed before execution.
C++ selected the existing BFD linker without exposing `/etc/alternatives`.

The report confirms `saved_player_data_unchanged: true`. The dashboard and
question-history checksums were also unchanged when recording this result.
These are nine protected playability smoke checks, not a claim that the complete
regression suite or an independent security audit has passed. Codex's own
restricted environment remains unable to perform these kernel integration flows.

Launch from the normal Fedora terminal with:

```bash
bash /home/alahmed/CODE_BREAKER_CAMPAIGN/CODE_BREAKER_IEEE/start.sh
```

`start.sh` uses the same transient delegated user-scope launcher and mandatory
isolation self-check as verification. No protection bypass is required.


## Visual and local preview update

- Added stage palettes, animated energy and gate effects, brief movement afterglow, smooth stage progress, menu mission cards and additional editor token colors.
- Added F10 preview, PageUp/PageDown stage navigation, F7/F8 challenge preview, F9 stage-clear preview, F4 effect preview, and F3 reduced motion.
- Preview score saving is blocked, including after preview is disabled until a fresh normal game. Preview starts do not write question history. Busy runner futures cannot be discarded by preview navigation.
- Headless UI regression test passed: all three stage palettes and rendering, shortcut navigation, wrapping, async navigation guards, timer freeze, leaderboard/history isolation, normal timer and result entry restoration.
- Rendered 120 headless frames in about 1 second in this environment; this is a smoke check, not a desktop FPS guarantee.
- Existing policy suite: 39 checks passed, one integration check skipped, two checks could not run because this environment is root and has no bubblewrap. No security code was changed to accommodate this environment.
- runner.py, execution_isolation.py, local_runtime.py, local.sh, start.sh, compiler support, question generators, scoring, and original data files are byte-for-byte preserved in the delivered archive.
- The earlier user's nine local language verification results remain historical evidence for the unchanged runner. Native execution of this visual update was not re-verified here. Run bash local.sh verify on Fedora for an end-to-end check.

## Material, sprite and in-place admin update

F10 is now an in-place flag toggle and transient notification. Explicit regression coverage compares maze and gate object identities, full maze/gate values, player position, level, questions, timer, score, hearts, draft/cursor, paused/editor modes, random-generator state, persisted files and pending runner future. F10 in the menu does not start a game. No persistent admin-shortcut HUD remains.

Replaced side menu cards with open space and centered controls. Added generated sprite atlases, walking directions, beveled wall/floor materials, faceted energy crystals and wall-occluded player light. All artwork uses the existing pygame-ce renderer; no extra runtime packages or security configuration are required.

UI regression suites test_admin_state.py and test_visual_preview.py passed headlessly. Rendered and inspected menu, stages and editor. A 120-frame render smoke check took about 1.4 seconds here; not a guarantee of user-device FPS. Native language execution was not rerun in this environment. The security runner, question generators, normal scoring and original saved data remain byte-identical to the supplied version.


## Robot artwork clarity

Rebuilt the robot from 512px source artwork before downsampling. The menu now uses a dedicated transparent 256x256 hero image, cached once at its 128x128 display size, rather than enlarging a 64x64 gameplay frame. Rebuilt all three movement atlases with the same layout and smoother edges. Menu rendering and in-place admin regression checks passed. No gameplay, question, execution or security files changed.
