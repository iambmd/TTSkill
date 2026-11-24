"""The languages the coaching is written in (a job's `lang`: English or Vietnamese), and the
fixed text the app puts around the AI's words: video labels, Coach's plan, the offline cards.

English is the default everywhere, and its strings here are the app's existing wording, so an
English job is unchanged. Table tennis terms follow docs/glossary_vi.md."""
from __future__ import annotations

LANGS = ("en", "vi")


def norm(lang: str | None) -> str:
    """A known language code, else English (old jobs and callers that never sent one)."""
    return lang if lang in LANGS else "en"


# The table tennis terms Vietnamese players use: every row of docs/glossary_vi.md (EN, VI), in
# order. Claude gets all of them for lang="vi"; tests/test_i18n.py fails if the two differ.
GLOSSARY: list[tuple[str, str]] = [
    ('forehand', 'thuận tay'),
    ('backhand', 'trái tay'),
    ('stroke', 'cú đánh'),
    ('topspin / loop', 'giật (topspin)'),
    ('forehand topspin', 'giật thuận tay'),
    ('backhand topspin', 'giật trái tay'),
    ('loop against backspin', 'giật bóng xoáy xuống'),
    ('forehand loop vs backspin', 'giật bóng xoáy xuống thuận tay'),
    ('drive', 'đôi công'),
    ('forehand drive', 'đôi công thuận tay'),
    ('push', 'gò'),
    ('flick', 'vẩy'),
    ('block', 'chặn bóng / chặn'),
    ('chop', 'cắt bóng / cắt'),
    ('serve', 'giao bóng'),
    ('third ball', 'bóng thứ ba'),
    ('counter-hit', 'phản công'),
    ('footwork', 'bộ chân'),
    ('split step', 'nhún bật'),
    ('rally', 'pha bóng'),
    ('highlights', 'pha bóng hay (nhất)'),
    ('full match', 'cả trận'),
    ('dead time', 'thời gian chết'),
    ('point', 'điểm'),
    ('ball contact (sound)', 'tiếng chạm bóng'),
    ('bounce', 'nảy / đỉnh nảy'),
    ('net', 'lưới'),
    ('table', 'bàn'),
    ('opponent', 'đối thủ'),
    ('drill', 'bài tập'),
    ('coach', 'HLV (huấn luyện viên)'),
    ('pro (player)', 'VĐV (vận động viên) chuyên nghiệp'),
    ('grip', 'cầm vợt / kiểu cầm vợt'),
    ('shakehand', 'cầm ngang'),
    ('penhold', 'cầm dọc'),
    ('bat hand', 'tay cầm vợt'),
    ('right-handed / left-handed', 'tay phải / tay trái'),
    ('stance', 'tư thế đứng'),
    ('ready position', 'tư thế chuẩn bị'),
    ('backswing', 'lăng vợt'),
    ('swing path', 'quỹ đạo vung vợt'),
    ('contact point', 'điểm tiếp xúc'),
    ('follow-through', 'vung theo'),
    ('recovery', 'về tư thế'),
    ('brush', 'miết'),
    ('closed / open bat angle', 'mặt vợt úp / mở'),
    ('knee bend', 'khuỵu gối'),
    ('elbow', 'khuỷu tay'),
    ('forearm', 'cẳng tay'),
    ('wrist', 'cổ tay'),
    ('toss (serve)', 'tung bóng'),
    ('cue', 'điểm cần học / gợi ý'),
    ('spin', 'xoáy'),
    ('topspin', 'xoáy lên'),
    ('backspin', 'xoáy xuống'),
    ('sidespin', 'xoáy ngang'),
    ('speed', 'tốc độ'),
    ('control', 'kiểm soát'),
    ('rubber', 'mặt vợt'),
    ('blade', 'cốt vợt'),
    ('sponge', 'mút'),
    ('sponge thickness', 'độ dày mút'),
    ('inverted', 'mặt trơn'),
    ('short pips', 'gai ngắn'),
    ('long pips', 'gai dài'),
    ('anti-spin', 'chống xoáy (anti)'),
    ('hardness', 'độ cứng'),
    ('official store', 'cửa hàng chính hãng'),
    ('beginner', 'mới chơi'),
    ('intermediate', 'trung bình'),
    ('advanced', 'nâng cao'),
]


def _terms() -> str:
    return "; ".join(f"{en} = {vi}" for en, vi in GLOSSARY)


def instruction(lang: str | None) -> str:
    """The language rule for a Claude call, or "" for English. It goes in the user turn, after
    the cached system prompt, so the cache serves both languages."""
    if norm(lang) == "en":
        return ""
    return ("\n\nLanguage: write every text the user reads (summary, headline, grip, stance, swing_path, "
            "contact_point, follow_through, card and step titles, lines, highlight_words, callouts, recap, "
            "drill) in natural Vietnamese, the way a Vietnamese club coach talks. Use the terms Vietnamese "
            f"players use, exactly as listed (English = Vietnamese): {_terms()}. Use \"tấn công\" only for "
            "attack in general, never for the drive stroke (đôi công). Keep player, product and brand names as "
            "they are. Keep JSON keys "
            "and the fixed values (moment, stroke, stroke_type, handedness) in English. highlight_words "
            "must be words copied from the Vietnamese lines. Titles stay two or three words and lines "
            "stay short (at most ~50 characters).")


_TEXT: dict[str, dict[str, str]] = {
    "en": {
        # The breakdown video's burned-in labels.
        "paused": "PAUSED",
        "cues": " CUES TO COPY",
        "try_this": "TRY THIS",
        "default_drill": "Shadow the stroke 20 times, checking each cue.",
        # Coach's plan and progress.
        "todo.download": "Download the video",
        "todo.rallies": "Find the rallies",
        "todo.reel": "Cut the best rallies",
        "todo.pose": "Track you at your {noun}s",
        "todo.pros": "Find the pros closest to you",
        "todo.coach": "Write the coaching",
        "todo.render": "Render your {noun}",
        "plan.measure": "Measure your {noun} with MediaPipe",
        "plan.match": "Find the pros closest to your {noun}",
        "plan.cards": "Write the coaching cards and render your {noun}",
        "plan.summary": "Sum up what to work on",
        "noun.forehand": "forehand",
        "noun.backhand": "backhand",
        "noun.stroke": "stroke",
        "msg.planning": "Planning...",
        "msg.download": "Downloading the video...",
        "msg.listening": "Listening for ball contacts...",
        "msg.pose": "Tracking you at your {noun}s...",
        "msg.pros": "Comparing you with the pros...",
        "msg.coach": "Writing your coaching...",
        "msg.render": "Rendering your {noun}...",
        "msg.cutting": "Cutting {n} rallies...",
        "msg.done": "Done.",
        "no_rallies": "No rallies were heard, so there is no reel. Film closer to the table, with the sound on.",
        # Coach's videos.
        "out.top": "Top {n} rallies",
        "out.all": "All {n} rallies",
        "out.top_summary": "{s} s, most shots first",
        "out.all_summary": "{s} s, dead time cut",
        "out.breakdown": "{stroke} breakdown",
        "out.match": "You play like {name}",
        # Coaching notes and the offline cards' summary.
        "notes.fix": "Biggest fix",
        "notes.drill": "Drill",
        "offline.measured": "Your {stroke}, measured at contact: {seen}.",
        "offline.stroke": "Your {stroke}.",
        "offline.elbow": "elbow about {deg}°",
        "offline.knees": "knees about {deg}°",
        "offline.like": "You play most like {name} ({score}% body match).",
        "offline.first": "What to work on first",
    },
    "vi": {
        "paused": "TẠM DỪNG",
        "cues": " ĐIỂM CẦN HỌC",
        "try_this": "THỬ BÀI TẬP",
        "default_drill": "Vung tay không 20 lần, kiểm tra từng điểm.",
        "todo.download": "Tải video",
        "todo.rallies": "Tìm các pha bóng",
        "todo.reel": "Cắt những pha bóng hay nhất",
        "todo.pose": "Theo dõi bạn ở các cú {noun}",
        "todo.pros": "Tìm VĐV giống bạn nhất",
        "todo.coach": "Viết nhận xét",
        "todo.render": "Dựng video cú {noun}",
        "plan.measure": "Đo cú {noun} của bạn bằng MediaPipe",
        "plan.match": "Tìm VĐV giống cú {noun} của bạn nhất",
        "plan.cards": "Viết thẻ nhận xét và dựng video cú {noun}",
        "plan.summary": "Tóm tắt những điều cần tập",
        "noun.forehand": "thuận tay",
        "noun.backhand": "trái tay",
        "noun.stroke": "đánh",
        "msg.planning": "Đang lập kế hoạch...",
        "msg.download": "Đang tải video...",
        "msg.listening": "Đang nghe tiếng chạm bóng...",
        "msg.pose": "Đang theo dõi bạn ở các cú {noun}...",
        "msg.pros": "Đang so sánh bạn với các VĐV...",
        "msg.coach": "Đang viết nhận xét...",
        "msg.render": "Đang dựng video cú {noun}...",
        "msg.cutting": "Đang cắt {n} pha bóng...",
        "msg.done": "Xong.",
        "no_rallies": "Không nghe thấy pha bóng nào nên không có video pha bóng hay. Hãy quay gần bàn hơn và bật âm thanh.",
        "out.top": "{n} pha bóng hay nhất",
        "out.all": "Cả {n} pha bóng",
        "out.top_summary": "{s} giây, pha nhiều bóng nhất trước",
        "out.all_summary": "{s} giây, đã bỏ thời gian chết",
        "out.breakdown": "Phân tích {stroke}",
        "out.match": "Bạn đánh giống {name}",
        "notes.fix": "Lỗi cần sửa nhất",
        "notes.drill": "Bài tập",
        "offline.measured": "Cú {stroke} của bạn, đo lúc tiếp xúc bóng: {seen}.",
        "offline.stroke": "Cú {stroke} của bạn.",
        "offline.elbow": "khuỷu tay khoảng {deg}°",
        "offline.knees": "đầu gối khoảng {deg}°",
        "offline.like": "Bạn giống {name} nhất ({score}% vóc dáng).",
        "offline.first": "Cần tập trước tiên",
    },
}

# Pro match: the form notes, the penhold warning, the title cards. English is the existing wording.
MATCH = {
    "en": dict(
        note="Your {what} {verb} {deg} {direction} at {phase} than {pro}'s.",
        what={"elbow": "elbow", "shoulder": "bat arm", "knee": "legs", "trunk_turn": "shoulders"},
        more={"elbow": "straighter", "shoulder": "higher", "knee": "straighter (less knee bend)",
              "trunk_turn": "more turned"},
        less={"elbow": "more bent", "shoulder": "lower", "knee": "more bent", "trunk_turn": "less turned"},
        phase={"the backswing": "the backswing", "contact": "contact", "the finish": "the finish"},
        penhold=("{name} plays penhold, so the backhand technique differs from shakehand. "
                 "Use {name}'s forehand as reference, and be careful copying the backhand."),
        card_rank="#{rank} MATCH · {stroke}", card_body="body match", card_hand="{hand}-handed",
        card_no_clip="No {stroke} clip of {name} yet.",
        grips={"shakehand": "shakehand", "penhold": "penhold"}),
    "vi": dict(
        note="{what} của bạn {direction} {deg} so với {pro} {phase}.",
        what={"elbow": "Khuỷu tay", "shoulder": "Tay cầm vợt", "knee": "Chân", "trunk_turn": "Vai"},
        more={"elbow": "thẳng hơn", "shoulder": "cao hơn", "knee": "thẳng hơn (khuỵu gối ít hơn)",
              "trunk_turn": "xoay nhiều hơn"},
        less={"elbow": "gập hơn", "shoulder": "thấp hơn", "knee": "gập hơn", "trunk_turn": "xoay ít hơn"},
        phase={"the backswing": "lúc lăng vợt", "contact": "lúc tiếp xúc bóng", "the finish": "lúc kết thúc"},
        penhold=("{name} cầm dọc, nên kỹ thuật trái tay khác với cầm ngang. Hãy lấy cú thuận tay của "
                 "{name} làm mẫu, và cẩn thận khi bắt chước cú trái tay."),
        card_rank="#{rank} GIỐNG BẠN · {stroke}", card_body="giống vóc dáng", card_hand="tay {hand}",
        card_no_clip="Chưa có video {stroke} của {name}.",
        grips={"shakehand": "cầm ngang", "penhold": "cầm dọc"}),
}
HANDS_VI = {"left": "trái", "right": "phải"}
# A pro's equipment_notes (data/players/players.json) in Vietnamese, by pro id.
EQUIPMENT_NOTES_VI = {
    "sabine-winter": ("Sabine Winter dùng mặt chống xoáy (anti) ở trái tay, nên kỹ thuật trái tay của cô khác "
                      "với mặt trơn thông thường. Hãy lấy cú thuận tay của cô làm mẫu, và cẩn thận khi bắt "
                      "chước cú trái tay."),
}

# Stroke names in Vietnamese (the English ones are technique.strokes labels).
STROKES_VI = {
    "forehand": "thuận tay", "backhand": "trái tay", "serve": "giao bóng", "flick": "vẩy",
    "block": "chặn bóng", "footwork": "bộ chân", "chop": "cắt bóng",
    "forehand_topspin": "giật thuận tay", "forehand_drive": "đôi công thuận tay",
    "forehand_loop_backspin": "giật bóng xoáy xuống thuận tay", "backhand_topspin": "giật trái tay",
    "backhand_flick": "vẩy trái tay", "backhand_push": "gò trái tay", "backhand_block": "chặn trái tay",
    "forehand_block": "chặn thuận tay",
}


def t(lang: str | None, key: str, **values) -> str:
    return _TEXT[norm(lang)][key].format(**values)


def stroke_label(key: str, lang: str | None) -> str:
    """A stroke's display name: technique.strokes' English label, or the Vietnamese name."""
    from technique.strokes import label

    if norm(lang) == "vi" and key in STROKES_VI:
        return STROKES_VI[key]
    return label(key)
