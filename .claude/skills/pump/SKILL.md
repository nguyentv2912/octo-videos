---
name: "pump"
description: "Gọi bằng /pump: dựng video 9:16 Mr PUMP từ giao dịch Solana thật (số dư ví trước/sau, PNL SOL) bằng script pump.py rồi hẹn đăng chỉ Instagram mrpumpsolana qua Buffer lúc 5h-10h-15h-20h, tối đa 4 bài/ngày."
---

# /pump — video replay giao dịch Mr PUMP và hẹn giờ đăng

## Mô tả công việc
Nhận nội dung từ người dùng (ảnh bảng giao dịch, link ví và pair) → dựng 1 video dọc 9:16, 20s, có nhạc từ giao dịch on-chain thật → đưa lên link công khai → hẹn đăng Instagram `mrpumpsolana` (chỉ kênh này) qua Buffer → báo lại bằng tiếng Việt.
- Kết quả giao: file mp4, caption tiếng Anh theo công thức, lịch đăng (giờ Việt Nam) và trạng thái bài.
- Lịch: khung cố định 05:00, 10:00, 15:00, 20:00, tối đa 4 bài/ngày, mỗi bài một video khác nhau.
- Ngoài phạm vi: chỉ đăng Instagram `mrpumpsolana`; không đăng TikTok, không đăng tài khoản Instagram khác, không đăng cho OCTO, không tự nối tài khoản mạng xã hội, không hứa lợi nhuận.

Mr PUMP là app/thương hiệu riêng của người dùng, tách biệt hoàn toàn với OCTO AI (kênh, kho lưu, nội dung đều riêng). Video replay giao dịch ON-CHAIN THẬT của một ví Solana bằng giao diện kiểu ví di động. Trả lời người dùng bằng tiếng Việt, ngắn gọn. Khi người dùng đưa nội dung (ảnh bảng giao dịch, link ví/pair), chạy trọn quy trình dưới đây: dựng video, rồi hẹn giờ đăng, trừ khi họ chỉ nói dựng.

## Đầu vào
Ảnh chụp bảng giao dịch (Solscan/DexScreener) và/hoặc link `solscan.io/account/<ví>` và `dexscreener.com/solana/<pair>`. Thiếu gì thì dùng cái có, không hỏi lại trừ khi không xác định được ví hoặc token. Ảnh thường tính bằng USD, dùng để đối chiếu và suy ra giá SOL.

## Quy tắc cố định cho video
- 1080x1920, 30fps, đúng 20s. Nhạc nền sôi động 120 BPM, sfx mua/bán khớp đúng thời điểm lệnh.
- Mọi con số lãi/lỗ bằng SOL. USD chỉ là phụ. Không viết ký hiệu $ trước số SOL.
- Luôn hiển thị số dư ví TRƯỚC và SAU từng lệnh: thẻ ticket "WALLET a → b", thanh số dư dưới đáy đổi đúng theo từng lệnh, thẻ PNL cuối ghi số dư đầu → cuối.
- Nếu số dư thay đổi giữa hai lệnh mà không do lệnh mua/bán thì hiện tag "−X SOL moved out" (hoặc "in"). Chỉ nêu sự thật số dư, không đoán nguyên nhân.
- Không dùng logo thương hiệu thật (Binance, Phantom, Telegram...), không ghi chữ "Phantom". Logo là bò Mr PUMP. Thiếu avatar token thì vẽ placeholder (hình kim cương trên nền gradient) và báo người dùng.
- Nhãn trung thực: giá dựng lại từ swap on-chain thì ghi "5m price · rebuilt from on-chain swaps". Bảng trending là minh họa, mức tăng của token chỉ tính trong khoảng dữ liệu có.
- Tên file: `MrPUMP_<TOKEN>_v<N>.mp4`. Mỗi yêu cầu chỉ render đầy đủ một lần (~30s).

## Script: `pump.py` (dữ liệu → video có nhạc, một lệnh)
Script gộp toàn bộ bước dựng hình, nhạc và ghép âm thanh, nằm trong kho `nguyentv2912/octo-videos` tại `mrpump/tools/pump.py` (logo ở `mrpump/assets/`, dữ liệu mẫu `mrpump/tools/example_data.json`). Đây là bản dùng chính, không cần dựng lại từ mô tả.
1. Lấy script: chạy ngay trong kho `octo-videos` (Claude Code mở kho này), script ở `mrpump/tools/pump.py`, không cần clone. Nếu đang ở nơi khác thì `git clone --depth 1 https://github.com/nguyentv2912/octo-videos` rồi chạy từ đó. Cần Pillow, numpy, ffmpeg và font Inter trong `/usr/share/fonts/opentype/inter`.
2. Chuẩn bị `RAW.json`: `{"sup": <supply>, "trades": [{"side": "BUY"|"SELL", "t": <unix>, "sol": <SOL>, "tok": <token>, "usd": <USD>, "pre": <số dư ví SOL trước lệnh>, "post": <sau lệnh>}], "samples": [[<unix>, <giá USD/token>], ...]}` (samples lấy từ bước đường giá bên dưới).
3. `python3 -I mrpump/tools/pump.py prep RAW.json DATA.json` tạo `DATA.json` (nến 5 phút, chèn giá lệnh thật, tính giá SOL, nội suy bucket thiếu).
4. Xem trước vài khung: `python3 -I mrpump/tools/pump.py render DATA.json out.mp4 --token <TÊN> --quote <TOKEN QUOTE> --wallet-short "<ví rút gọn>" --logo-dir mrpump/assets --keys 5 9 11 13 16 --keydir <thư mục>` (chỉ xuất PNG), rồi xem và sửa chồng chữ.
5. Render đầy đủ: cùng lệnh, bỏ `--keys`. Khoảng 35 giây, ra mp4 1080x1920, đúng 20s, có nhạc. `--no-audio` nếu chỉ cần hình.
6. Script hỗ trợ số lệnh mua bất kỳ và tối đa 4 nhóm lệnh bán (nhiều hơn sẽ tự gộp thành 4 nhóm). Tự tính timeline theo nhịp 120 BPM, đổi số dư đúng từng lệnh và hiện tag "in/moved out" khi số dư đổi giữa hai lệnh. Đã kiểm tra với 1 mua/2 bán và 2 mua/4 bán.
7. `--trending` tùy chọn (file JSON các dòng sym/price/mc/h24), không có thì dùng danh sách minh họa mặc định. Thiếu file logo thì script vẽ logo tạm.
Chỉ còn phần lấy dữ liệu on-chain (Make/RPC) là làm tay theo các bước dưới đây; các bước dựng hình/nhạc 4–8 bên dưới giờ do script làm.

## Quy trình dựng video
1. **Số liệu ví** (bước chậm nhất): shell và WebFetch thường không ra được host ngoài allowlist, nên gọi RPC Solana công khai qua scenario Make. Tái dùng tài nguyên đã có, không tạo mới: scenario 6990152 "Mr PUMP - wallet trades read-only" (on-demand), data store 198535 (giới hạn 1 MiB, ghi đè key, xóa key cũ khi đầy), organizationId 2273437, team 189786. Công thức module: `http:MakeRequest` v4 (authenticationType noAuth, contentType json, inputMethod jsonString, parseResponse false, stopOnHttpError false) rồi `datastore:AddRecord` v1 (datastore là SỐ 198535, overwrite true, data.body "{{N.data}}"). `scenarios_update` thay cả blueprint; `scenarios_run` responsive true; đọc kết quả bằng `data-store-records_list`. RPC `api.mainnet-beta.solana.com`: dùng `maxSupportedTransactionVersion: 1`, tối đa 5 getTransaction mỗi lượt, chờ 50–75s giữa các lượt vì hay 429. Với tx v0, gộp accountKeys + loadedAddresses (writable, readonly) trước khi tìm chỉ số của ví.
2. **Lệnh thật**: từ preBalances/postBalances của ví lấy SOL vào/ra và số dư trước/sau từng lệnh; từ pre/postTokenBalances lấy số token. Đối chiếu USD trong ảnh để suy ra giá SOL và neo giá token. Lưu `data.json` (trades: side,t,sol,tok,usd,px,mc,wb=[pre,post]; m5: nến 5 phút; SUP; SOL_BUY; SOL_SELL; bal).
3. **Đường giá**: nếu không có nến sàn, dựng giá từ số dư vault của pool (token quote / token base) tại các tx lấy mẫu ~5 phút, đổi sang USD bằng nến GeckoTerminal của cặp quote/SOL rồi co giãn cho khớp giá ở các lệnh thật. Chèn đúng giá lệnh thật vào nến chứa lệnh để headline MC khớp ticket. Supply = fdv / priceUsd (DexScreener). Bucket thiếu thì nội suy.
4. **Dựng hình**: Pillow vẽ từng khung rồi pipe vào ffmpeg (libx264 crf18 veryfast, ghi ra .part.mp4 rồi đổi tên). Cảnh: màn hình chủ mở app → tab Trade → trang token → bấm Buy → tua lại → biểu đồ nến 5 phút có marker B/S, timelapse giá trị vị thế, ticket từng lệnh, ba ô Invested/Realized/Multiple, thanh số dư → thẻ PNL neon (TOTAL BUY/SELL, PNL, ROI, MULTIPLE, HELD, WALLET BALANCE). Việc này do `pump.py` làm (xem mục Script). Pillow: vẽ trên canvas RGB, trộn bằng Image.blend hoặc paste có mask; font Inter, cỡ từ 40 dùng InterDisplay.
5. **Số lệnh**: `pump.py` tự xử lý số lệnh mua bất kỳ và tối đa 4 nhóm bán. Chỉ sửa script khi cần đổi hành vi.
6. **Mẫu timeline** (nhịp 0.5s, lưới 0.2 + 0.5k): lệnh mua đầu ~4.7s; timelapse vị thế 5.7→9.2s; lệnh bán đầu ở nhịp ~10.2s (điểm drop); các lệnh bán cách nhau tối thiểu ~2.5s; thẻ PNL xuất hiện ở lệnh bán cuối + ~2.5s và giữ tới 20s. Thêm lệnh thì nén timelapse chứ không kéo dài video.
7. **Bố cục đã chốt** (tránh chồng chữ): bảng danh sách lệnh ở góc dưới phải trong biểu đồ, nhãn ENTRY ở bên phải, nhãn AVG SELL ở bên trái phía trên, marker S xếp thành hàng phía trên, số cột nến co theo số nến đang hiện (tối thiểu 16, tối đa 36), ticket hiện 2s, tag "moved out" nằm giữa thanh số dư. Tên token/ví trong thẻ cuối phải co cỡ chữ để không đè icon.
8. **Nhạc**: `pump.py` tự tạo (numpy synth) và ghép vào video; mốc mua/bán/thẻ PNL tự khớp timeline, lệnh bán là drop, thẻ PNL có boom + tick đếm + hợp âm. Lệnh mux bên trong script: `ffmpeg -y -i silent.mp4 -i music.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest`.
9. **Kiểm tra trước khi giao**: (a) tính lại bằng code: PNL = tổng SOL bán − tổng SOL mua, ROI, multiple, USD khớp ảnh; (b) render vài khung chính (ngay sau mua, giữa timelapse, sau mỗi lệnh bán, thẻ PNL) rồi xem, sửa chồng chữ; (c) ffprobe: 1080x1920, đúng 20s, có audio.
10. **Giao**: gửi mp4 bằng SendUserFile kèm tóm tắt tiếng Việt: số dư trước → sau từng lệnh, tổng mua/bán, PNL SOL, ROI, multiple, thời gian giữ; và lưu ý (giá dựng lại, market cap từ DexScreener, giá SOL suy ra từ ảnh, avatar placeholder, trending minh họa).

## Đăng và hẹn giờ (chỉ Instagram `mrpumpsolana` qua Buffer)
Buffer chỉ nhận video qua link tải trực tiếp, công khai. Quy trình:
1. **Kiểm tra kênh** bằng `get_account` rồi `list_channels` (organizationId `66f249d4ff57a3cad2a28053`, "My Organization"). Danh sách có thể đã đổi, luôn xác nhận lại trước khi đăng. Kênh duy nhất để đăng: Instagram `mrpumpsolana` (id `6af42a2b62b70b94b0f2305e`). Các kênh khác trong Buffer (Instagram `pumpmeme.crypto`, TikTok `mr.pump395`) không dùng cho /pump. Gói Buffer giới hạn 3 kênh và 10 bài hẹn giờ cùng lúc (kênh YouTube Mr PUMP đã bị gỡ để nhường chỗ). Kênh nào chưa hiện thì báo người dùng nối vào Buffer (hoặc Metricool); mình không tự nối được tài khoản.
2. **Đưa video lên link công khai**: tạm dùng kho công khai `nguyentv2912/octo-videos`, thư mục `mrpump/` (không đụng video OCTO và workflow `octo-daily`). Trong kho đang mở: copy mp4 vào `mrpump/`, commit rồi `git fetch origin main && git rebase origin/main && git push origin main`. Cuối commit thêm đúng dòng attribution do hệ thống yêu cầu. Link: `https://raw.githubusercontent.com/nguyentv2912/octo-videos/main/mrpump/<tên file>.mp4`. Video lên đây là công khai, chỉ đưa video định đăng. Sẽ tốt hơn nếu người dùng tạo kho riêng `mrpump-videos` (phiên làm việc không tự tạo được kho mới); khi có thì dùng kho đó thay vì lẫn với OCTO.
3. **Caption** (tiếng Anh, đúng công thức của người dùng): dòng 1 `Claude + Meme coin = Mr Pump.`; dòng 2 một câu hỏi dạng `Do you want to ...?` (đổi theo nội dung video, đó là tiêu đề chính); cách một dòng; 5 hashtag, mặc định `#solana #memecoin #crypto #onchain #mrpump`. Không viết ký hiệu $ trước số SOL, không hứa lợi nhuận. Nên thêm câu "Not financial advice" và nhắc người dùng điều này, nhưng chỉ thêm khi họ đồng ý vì công thức không có.
4. **Tạo bài** bằng `create_post`: `channelId` luôn là `6af42a2b62b70b94b0f2305e`; `metadata.instagram = {type: reel, shouldShareToFeed: true}`; `assets` là `[{video:{url}}]`; `schedulingType: automatic`. Lần đầu với kênh mới, tạo bản nháp (`saveToDraft: true`) để kiểm tra link, rồi dùng `edit_post` với `mode: customScheduled`, `dueAt`, `saveToDraft: false` (mang theo assets và metadata). Dùng `dueAt` kèm offset `+07:00`.
5. **Khung giờ cố định, tối đa 4 bài/ngày**: 05:00, 10:00, 15:00, 20:00 giờ Việt Nam. Chọn khung kế tiếp còn trống, kiểm tra trùng bằng `list_posts` trước khi hẹn. Lịch đăng cố định của kênh trong Buffer không đặt được qua API (múi giờ kênh đang là Europe/London), nên luôn hẹn bằng `customScheduled` với giờ rõ ràng, và nhắc người dùng có thể tự đặt múi giờ Việt Nam cùng 4 khung này trong Buffer nếu muốn dùng hàng đợi.
6. **Chỉ đăng `mrpumpsolana`**: không đăng cùng video lên TikTok hay Instagram khác, trừ khi người dùng đổi yêu cầu.
7. **Báo lại**: nói kênh, giờ đăng (giờ Việt Nam), caption và trạng thái "scheduled". 4 bài/ngày cần 4 video/ngày; Buffer chỉ cho tối đa 10 bài hẹn giờ cùng lúc nên chỉ hẹn trước khoảng 2–3 ngày.

## Lưu ý về lưu trữ
Script chính nằm trong kho `octo-videos/mrpump/tools/pump.py`; bản sao trong môi trường làm việc có thể mất sau phiên. Scenario Make và data store giữ lại để tái dùng, chỉ nhắc xóa khi người dùng muốn dọn.