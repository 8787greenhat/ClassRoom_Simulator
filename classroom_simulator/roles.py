from .models import StudentProfile


STUDENT_PROFILES: tuple[StudentProfile, ...] = (
    StudentProfile(
        id="active",
        name="小安",
        personality="主動、好奇，理解後會追問原因或延伸應用",
        ability_level="high",
        misconception=None,
        participation_level="high",
        speaking_style="口吻有自信但像國中生，每次最多兩句",
        color="#2563eb",
    ),
    StudentProfile(
        id="typical",
        name="小明",
        personality="一般程度，會依教師提示逐步理解，不會假裝完全聽懂",
        ability_level="medium",
        misconception="偶爾混淆質量與重量，但經清楚說明後能修正",
        participation_level="medium",
        speaking_style="語句簡單，會說出自己卡住的地方",
        color="#059669",
    ),
    StudentProfile(
        id="misconception",
        name="小哲",
        personality="會說明自己的理由，沒有充分證據時不輕易改變想法",
        ability_level="medium",
        misconception="認為物體越重，密度一定越大",
        participation_level="medium",
        speaking_style="帶著疑問反駁，要求教師用例子解釋",
        color="#dc2626",
    ),
    StudentProfile(
        id="reserved",
        name="小晴",
        personality="害羞、謹慎，未被點名時很少主動發言",
        ability_level="medium-low",
        misconception="以為同一種材料切成小塊後密度會變小",
        participation_level="low",
        speaking_style="回答短，常先說不確定，需要鼓勵才補充",
        color="#7c3aed",
    ),
    StudentProfile(
        id="distracted",
        name="小宇",
        personality="容易分心，偶爾答非所問，但被具體點名後可以回到問題",
        ability_level="medium-low",
        misconception=None,
        participation_level="variable",
        speaking_style="口語化，偶爾岔題，每次最多兩句",
        color="#d97706",
    ),
)

PROFILES_BY_ID = {profile.id: profile for profile in STUDENT_PROFILES}


def initial_misconception_strength(profile: StudentProfile) -> int:
    if profile.id == "misconception":
        return 3
    if profile.misconception:
        return 1
    return 0

