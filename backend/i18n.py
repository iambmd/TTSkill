"""The languages the coaching is written in (a job's `lang`: English or Vietnamese), and the
fixed text the app puts around the AI's words: video labels, Coach's plan, the offline cards.

English is the default everywhere, and its strings here are the app's existing wording, so an
English job is unchanged. Table tennis terms follow docs/glossary_vi.md."""
from __future__ import annotations

LANGS = ("en", "vi")


def norm(lang: str | None) -> str:
    """A known language code, else English (old jobs and callers that never sent one)."""
    return lang if lang in LANGS else "en"


# The terms Vietnamese players use; the same list is in docs/glossary_vi.md for review.
_VI_TERMS = ("forehand = thuận tay, backhand = trái tay, rubber = mặt vợt, blade = cốt vợt, "
             "topspin = giật (or topspin), loop vs backspin = giật bóng xoáy xuống, drive = tấn công, "
             "push = gò, block = chặn, chop = cắt, flick = vẩy, serve = giao bóng, rally = pha bóng, "
             "footwork = bộ chân, backswing = lăng vợt, follow-through = vung theo, "
             "contact point = điểm tiếp xúc, ready position = tư thế chuẩn bị, stance = tư thế đứng, "
             "spin = xoáy, backspin = xoáy xuống, drill = bài tập, coach = HLV")


def instruction(lang: str | None) -> str:
    """The language rule for a Claude call, or "" for English. It goes in the user turn, after
    the cached system prompt, so the cache serves both languages."""
    if norm(lang) == "en":
        return ""
    return ("\n\nLanguage: write every text the user reads (summary, headline, grip, stance, swing_path, "
            "contact_point, follow_through, card and step titles, lines, highlight_words, callouts, recap, "
            "drill) in natural Vietnamese, the way a Vietnamese club coach talks. Use the terms Vietnamese "
            f"players use: {_VI_TERMS}. Keep player, product and brand names as they are. Keep JSON keys "
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

# Stroke names in Vietnamese (the English ones are technique.strokes labels).
STROKES_VI = {
    "forehand": "thuận tay", "backhand": "trái tay", "serve": "giao bóng", "flick": "vẩy",
    "block": "chặn bóng", "footwork": "bộ chân", "chop": "cắt bóng",
    "forehand_topspin": "giật thuận tay", "forehand_drive": "tấn công thuận tay",
    "forehand_loop_backspin": "giật thuận tay bóng xoáy xuống", "backhand_topspin": "giật trái tay",
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
