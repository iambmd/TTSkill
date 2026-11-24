# Thuật ngữ bóng bàn: Anh – Việt

Bảng này liệt kê mọi thuật ngữ bóng bàn mà TTSkill dùng trong giao diện tiếng Việt, trong video phân tích và trong lời nhận xét do AI viết. Các dòng ghi **Đã chốt** là quyết định cuối cùng của chủ sản phẩm (người Việt); những dòng khác vẫn có thể góp ý ở cột **Ghi chú**.

Cách sửa một thuật ngữ: đổi ở đây, trong `backend/i18n.py` (`GLOSSARY`, danh sách gửi cho Claude khi `lang="vi"`; `backend/tests/test_i18n.py` báo lỗi nếu hai nơi khác nhau), rồi ở `frontend/messages/vi.json` (giao diện), `backend/i18n.py` (nhãn video, kế hoạch của HLV) và `backend/technique/analyze.py` (`_TEMPLATES_VI`, các thẻ khi không có Claude).

*For a Vietnamese coach reviewing the app's terms. Product, brand and player names stay in English (TTSkill, TT Coach, Auto-Cut, Butterfly Tenergy 05, Ma Long...).*

## Cú đánh (strokes)

| EN | VI | Ghi chú (notes) |
| --- | --- | --- |
| forehand | thuận tay | Đúng như yêu cầu. Dùng cả "cú thuận tay". |
| backhand | trái tay | |
| stroke | cú đánh | "cú" đứng trước tên cú: "cú giật thuận tay". |
| topspin / loop | giật (topspin) | "Giật" là từ chính; "topspin" giữ nguyên khi nói về độ xoáy, ví dụ "Giật và topspin nặng". |
| forehand topspin | giật thuận tay | |
| backhand topspin | giật trái tay | |
| loop against backspin | giật bóng xoáy xuống | **Đã chốt.** |
| forehand loop vs backspin | giật bóng xoáy xuống thuận tay | **Đã chốt.** |
| drive | đôi công | **Đã chốt.** Cú đánh thẳng, ít xoáy. "Tấn công" chỉ dùng với nghĩa tấn công nói chung. |
| forehand drive | đôi công thuận tay | **Đã chốt.** |
| push | gò | "Gò trái tay". |
| flick | vẩy | "Vẩy trái tay". Một số người gọi là "búng". |
| block | chặn bóng / chặn | "Chặn trái tay", "chặn thuận tay". |
| chop | cắt bóng / cắt | Lối đánh phòng thủ xa bàn. |
| serve | giao bóng | |
| third ball | bóng thứ ba | Cú tấn công sau giao bóng. |
| counter-hit | phản công | |
| footwork | bộ chân | Cũng dùng "di chuyển chân". |
| split step | nhún bật | |

## Pha bóng và trận đấu (rallies and matches)

| EN | VI | Ghi chú |
| --- | --- | --- |
| rally | pha bóng | Theo yêu cầu: "pha bóng/loạt bóng". Chúng tôi dùng "pha bóng" ở mọi nơi. |
| highlights | pha bóng hay (nhất) | Video tổng hợp: "video pha bóng hay". |
| full match | cả trận | |
| dead time | thời gian chết | Lúc nhặt bóng, nghỉ giữa các điểm. |
| point | điểm | |
| ball contact (sound) | tiếng chạm bóng | Ứng dụng tìm pha bóng bằng âm thanh. |
| bounce | nảy / đỉnh nảy | "Chạm bóng ở đỉnh nảy". |
| net | lưới | |
| table | bàn | |
| opponent | đối thủ | |
| drill | bài tập | |
| coach | HLV (huấn luyện viên) | **Đã chốt.** Trên thanh menu cũng là "HLV". |
| pro (player) | VĐV (vận động viên) chuyên nghiệp | Viết tắt "VĐV" cho gọn trên điện thoại: "So với VĐV". |

## Kỹ thuật (technique)

| EN | VI | Ghi chú |
| --- | --- | --- |
| grip | cầm vợt / kiểu cầm vợt | |
| shakehand | cầm ngang | Phụ đề: "Kiểu bắt tay". |
| penhold | cầm dọc | Phụ đề: "Cầm như cầm bút". |
| bat hand | tay cầm vợt | "Tay phải", "tay trái". |
| right-handed / left-handed | tay phải / tay trái | Về người chơi: "VĐV tay trái". |
| stance | tư thế đứng | |
| ready position | tư thế chuẩn bị | |
| backswing | lăng vợt | "Lăng vợt ngắn". |
| swing path | quỹ đạo vung vợt | |
| contact point | điểm tiếp xúc | "Chạm bóng phía trước người". |
| follow-through | vung theo | Có khi dùng "kết thúc động tác". |
| recovery | về tư thế | |
| brush | miết | "Miết lên phía sau bóng". |
| closed / open bat angle | mặt vợt úp / mở | |
| knee bend | khuỵu gối | |
| elbow | khuỷu tay | |
| forearm | cẳng tay | |
| wrist | cổ tay | |
| toss (serve) | tung bóng | Luật: tung cao ít nhất 16 cm. |
| cue | điểm cần học / gợi ý | Ba gợi ý ngắn trong video phân tích. |

## Xoáy (spin)

| EN | VI | Ghi chú |
| --- | --- | --- |
| spin | xoáy | |
| topspin | xoáy lên | Khi nói về loại xoáy (không phải cú đánh). |
| backspin | xoáy xuống | |
| sidespin | xoáy ngang | |
| speed | tốc độ | |
| control | kiểm soát | |

## Dụng cụ (equipment)

| EN | VI | Ghi chú |
| --- | --- | --- |
| rubber | mặt vợt | Tính theo "mặt": "Ngân sách mỗi mặt". |
| blade | cốt vợt | |
| sponge | mút | |
| sponge thickness | độ dày mút | "OX" = không có mút. |
| inverted | mặt trơn | Mặt gai úp vào trong, bề mặt nhẵn. |
| short pips | gai ngắn | |
| long pips | gai dài | |
| anti-spin | chống xoáy (anti) | |
| hardness | độ cứng | |
| official store | cửa hàng chính hãng | |

## Trình độ (levels)

| EN | VI | Ghi chú |
| --- | --- | --- |
| beginner | mới chơi | |
| intermediate | trung bình | |
| advanced | nâng cao | |
