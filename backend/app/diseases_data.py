"""
Cơ sở tri thức bệnh học thú y chuẩn cho 9 bệnh ngoài da trên heo và cá thể khỏe mạnh.
Dữ liệu chuẩn hóa theo tài liệu khuyến cáo của Cục Thú Y và thực tế lâm sàng.
"""

DISEASES_DATA = {
    "VIRA_FMD": {
        "code": "VIRA_FMD",
        "name_vi": "Lở mồm long móng (FMD)",
        "name_en": "Foot-and-Mouth Disease",
        "pathogen": "Aphthovirus (Picornaviridae)",
        "urgency_level": "CRITICAL",  # CRITICAL (Đỏ), HIGH (Vàng), MODERATE (Xanh)
        "urgency_label": "Báo động đỏ - Nguy hiểm cấp tính",
        "transmission": "Lây lan siêu nhanh qua không khí, tiếp xúc dịch tiết mụn mủ, phân, xe vận chuyển và người nuôi.",
        "symptoms": [
            "Sốt cao 40 - 41.5 độ C, ủ rũ, biếng ăn.",
            "Xuất hiện mụn nước ở vành móng, kẽ móng, gót chân, mụn vỡ gây loét khiến heo đi khập khiễng hoặc quỳ gối.",
            "Mụn nước ở mõm, lưỡi, lợi gây chảy nhiều nước bọt có bọt trắng."
        ],
        "isolation_protocol": "Cách ly nghiêm ngặt toàn bộ dãy chuồng ngay lập tức. Báo cáo cơ quan thú y địa phương. Tuyệt đối không vận chuyển phân, heo ra vào trại.",
        "disinfection": "Phun sát trùng 2 lần/ngày bằng Iodine 2%, Vôi bột 10-20% rải lối đi, hoặc Virkon S 1%.",
        "treatment_protocol": [
            "Bệnh do virus, chưa có thuốc đặc trị diệt virus; can thiệp chính là nâng cao sức đề kháng và chống bội nhiễm.",
            "Rửa vết loét bằng nước lá chát (trà xanh, lá ổi) hoặc dung dịch thuốc tím KMnO4 0.1%, xanh Methylen 1%.",
            "Tiêm kháng sinh chống nhiễm trùng kế phát: Amoxicillin hoặc Oxytetracycline kết hợp Vitamin C + Hạ sốt Paracetamol/Analgine.",
            "Cho ăn cháo lỏng, bổ sung điện giải Gluco-KC."
        ]
    },
    "VIRA_POX": {
        "code": "VIRA_POX",
        "name_vi": "Bệnh đậu heo (Swinepox)",
        "name_en": "Swinepox",
        "pathogen": "Swinepox virus (Poxviridae)",
        "urgency_level": "CRITICAL",
        "urgency_label": "Báo động đỏ - Bệnh truyền nhiễm lây lan",
        "transmission": "Do rận heo (Haematopinus suis) truyền bệnh, hoặc qua vết trầy xước tiếp xúc mài đậu.",
        "symptoms": [
            "Ban đỏ hình tròn đường kính 1-3 cm ở vùng da non: bụng, háng, đùi non, tai.",
            "Nốt sần tiến triển thành mụn mủ, sau đó khô lại tạo vảy màu nâu đen sần sùi.",
            "Heo ngứa ngáy, cọ xát vào vách chuồng làm rách da dễ nhiễm trùng."
        ],
        "isolation_protocol": "Cách ly heo bệnh sang chuồng riêng. Tiêu diệt rận và ngoại ký sinh trùng trên toàn đàn.",
        "disinfection": "Sát trùng chuồng bằng dung dịch Benkocid hoặc Omnicide 1:200.",
        "treatment_protocol": [
            "Bôi xanh Methylen hoặc mỡ kháng sinh Tetracycline lên các nốt đậu bị loét.",
            "Tiêm kháng sinh phổ rộng Amox-Colis để phòng phụ nhiễm tụ cầu/liên cầu.",
            "Bổ sung B-Complex và Vitamin ADE giúp da nhanh tái tạo vảy."
        ]
    },
    "BACT_ERY": {
        "code": "BACT_ERY",
        "name_vi": "Bệnh đóng dấu lợn (Erysipelas)",
        "name_en": "Swine Erysipelas",
        "pathogen": "Erysipelothrix rhusiopathiae (Vi khuẩn)",
        "urgency_level": "HIGH",
        "urgency_label": "Nguy cơ cao - Cần can thiệp kháng sinh",
        "symptoms": [
            "Xuất hiện các mảng xuất huyết màu đỏ tía hình quả trám, hình vuông hoặc đa giác trên lưng, sườn, tai.",
            "Vết ban gồ cao hơn mặt da, sờ vào thấy cứng và nóng.",
            "Sốt cao 41-42 độ C, mắt đỏ, táo bón sau đó tiêu chảy, khó thở."
        ],
        "isolation_protocol": "Cách ly ngay các con có vết ban. Gom phân đốt hoặc ủ nhiệt sinh học.",
        "disinfection": "Vi khuẩn nhạy cảm với Cloramin B, Vôi bột 10%, Formalin 2%.",
        "treatment_protocol": [
            "Đặc trị bằng Penicillin G liều cao (20.000 - 30.000 UI/kg thể trọng) tiêm bắp ngày 2 lần trong 3-5 ngày.",
            "Có thể dùng Amoxicillin hoặc Ampicillin phối hợp.",
            "Tiêm hạ sốt Anagin + Vitamin C giải độc gan thận."
        ]
    },
    "BACT_GPD": {
        "code": "BACT_GPD",
        "name_vi": "Viêm da tiết dịch (Greasy Pig Disease)",
        "name_en": "Exudative Epidermitis",
        "pathogen": "Staphylococcus hyicus (Tụ cầu khuẩn)",
        "urgency_level": "HIGH",
        "urgency_label": "Nguy cơ cao - Bệnh nhiễm trùng da nặng ở heo con",
        "symptoms": [
            "Da nhờn dính, phủ lớp vảy nâu xám đen tiết dịch nhờn hôi ráp.",
            "Thường xuất hiện nhiều ở vùng mặt, mắt, tai, sau đó lan ra bụng và chân.",
            "Không ngứa rõ rệt nhưng heo gầy sút rất nhanh, mất nước và kiệt sức."
        ],
        "isolation_protocol": "Cách ly heo con mắc bệnh khỏi bầy, vệ sinh sàn chuồng úm khô ráo, tránh ẩm ướt.",
        "disinfection": "Rửa sàn chuồng bằng xà phòng sát khuẩn, xông khử trùng chuồng đẻ.",
        "treatment_protocol": [
            "Tắm rửa nhẹ cho heo bằng nước xà phòng sát trùng hoặc nước lá chanh/trà xanh.",
            "Xịt dung dịch Oxytetracycline hoặc bôi mỡ kháng sinh lên vết nhờn.",
            "Tiêm Penicillin, Amoxicillin hoặc Ceftiofur liên tục 3-4 ngày.",
            "Cho uống bù nước và điện giải Oresol pha mật ong hoặc Gluco-C."
        ]
    },
    "FUNG_RING": {
        "code": "FUNG_RING",
        "name_vi": "Bệnh nấm da / Lác đồng tiền (Ringworm)",
        "name_en": "Porcine Ringworm",
        "pathogen": "Microsporum nanum / Trichophyton spp. (Nấm)",
        "urgency_level": "MODERATE",
        "urgency_label": "Mức độ trung bình - Cần kiểm soát lây lan",
        "symptoms": [
            "Tổn thương da hình tròn hoặc bầu dục lan rộng theo hình nhẫn/vòng đồng tiền.",
            "Vùng giữa tổn thương có xu hướng lành, rìa ngoài có vảy gàu trắng xám gồ lên.",
            "Rụng lông cục bộ, da dày sừng nhẹ."
        ],
        "isolation_protocol": "Hạn chế nhốt chung mật độ dày. Bào tử nấm có thể lây sang người nuôi (bệnh truyền lây zoonosis).",
        "disinfection": "Đốt lông chuồng, quét dọn sạch vảy gàu, phun sát trùng bằng Sunfat đồng CuSO4 2% hoặc cồn Iod.",
        "treatment_protocol": [
            "Cạo sạch vảy gàu bám trên da rồi bôi cồn Iod 10% hoặc kem kháng nấm Ketoconazole / Clotrimazole.",
            "Tắm cho đàn bằng xà phòng có chứa lưu huỳnh hoặc dung dịch Enilconazole 0.2%.",
            "Giữ chuồng khô ráo, đón ánh nắng mặt trời trực tiếp."
        ]
    },
    "FUNG_ROSEA": {
        "code": "FUNG_ROSEA",
        "name_vi": "Bệnh vảy phấn hồng (Pityriasis Rosea)",
        "name_en": "Pityriasis Rosea",
        "pathogen": "Yếu tố di truyền / Miễn dịch lành tính",
        "urgency_level": "MODERATE",
        "urgency_label": "Mức độ nhẹ - Bệnh lành tính",
        "symptoms": [
            "Xuất hiện các nốt sẩn màu hồng nhỏ ở vùng bụng và đùi non heo 3-14 tuần tuổi.",
            "Các nốt kết nối thành hình vòng hoa, bờ viền gồ cao màu đỏ hồng, tâm vảy sáng.",
            "Heo không sốt, không ngứa, vẫn ăn uống và tăng trọng bình thường."
        ],
        "isolation_protocol": "Không cần cách ly gắt gao vì không lây nhiễm vi khuẩn/virus nguy hiểm.",
        "disinfection": "Vệ sinh chuồng trại thông thoáng sạch sẽ.",
        "treatment_protocol": [
            "Bệnh thường tự khỏi hoàn toàn sau 4 - 8 tuần mà không cần tiêm thuốc.",
            "Bôi kem chống viêm nhẹ hoặc xịt thuốc sát trùng tránh nhiễm trùng kế phát nếu heo cọ rách vảy.",
            "Bổ sung kẽm (Zinc) và Vitamin vào khẩu phần ăn giúp da phục hồi nhanh."
        ]
    },
    "PARA_MANGE": {
        "code": "PARA_MANGE",
        "name_vi": "Bệnh ghẻ sảy (Mange)",
        "name_en": "Sarcoptic Mange",
        "pathogen": "Sarcoptes scabiei var. suis (Cái ghẻ)",
        "urgency_level": "HIGH",
        "urgency_label": "Cần điều trị dứt điểm - Nguy cơ lây cả đàn",
        "symptoms": [
            "Ngứa ngáy dữ dội, heo liên tục lắc tai, cọ người vào thành chuồng đến chảy máu.",
            "Tập trung ở vành tai, mắt, cổ, lưng, chân; da dày cộm, nhăn nheo, sừng hóa.",
            "Heo chậm lớn, còi cọc do mất ngủ và stress liên tục."
        ],
        "isolation_protocol": "Cách ly heo bệnh; cái ghẻ bò từ con này sang con khác rất nhanh qua tiếp xúc và vách ngăn.",
        "disinfection": "Phun thuốc diệt ký sinh trùng lên tường, sàn chuồng và máng ăn.",
        "treatment_protocol": [
            "Tiêm Ivermectin hoặc Doramectin liều 1ml/33kg thể trọng tiêm dưới da, nhắc lại sau 14 ngày để diệt lứa trứng mới nở.",
            "Tắm hoặc xịt dung dịch Amitraz hoặc Deltamethrin toàn thân.",
            "Bôi mỡ lưu huỳnh vào các mảng ghẻ dày ở vành tai."
        ]
    },
    "ENV_DERM": {
        "code": "ENV_DERM",
        "name_vi": "Viêm da tiếp xúc / Môi trường (Dermatitis)",
        "name_en": "Contact / Environmental Dermatitis",
        "pathogen": "Hóa chất sát trùng nồng độ cao, amoniac từ nước tiểu, cọ xát sàn bê tông ráp",
        "urgency_level": "MODERATE",
        "urgency_label": "Khắc phục môi trường chuồng trại",
        "symptoms": [
            "Vùng da tiếp xúc sàn (khuỷu chân, bụng, ngực) đỏ rát, trợt biểu bì.",
            "Da sưng tấy nhẹ, có thể tiết dịch mỏng nhưng không có mụn nước hình kim cương.",
            "Chỉ xuất hiện trên các cá thể nằm ở khu vực ẩm bẩn hoặc cọ xát nhiều."
        ],
        "isolation_protocol": "Không lây truyền vi sinh vật, không cần cách ly nghiêm ngặt.",
        "disinfection": "Xả sạch hóa chất sát trùng dư thừa, kiểm tra độ dốc thoát nước của sàn chuồng.",
        "treatment_protocol": [
            "Rửa sạch vùng da tổn thương bằng nước muối sinh lý NaCl 0.9%.",
            "Bôi thuốc mỡ kẽm Oxyd hoặc dung dịch làm dịu da xịt Blue Spray.",
            "Trải thảm cao su hoặc rơm sạch khô lót sàn chỗ heo nằm."
        ]
    },
    "ENV_SUN": {
        "code": "ENV_SUN",
        "name_vi": "Cháy nắng da heo (Sunburn)",
        "name_en": "Sunburn / Photosensitization",
        "pathogen": "Tia cực tím (UV) mặt trời chiếu trực tiếp hoặc ăn thức ăn nhạy cảm ánh sáng",
        "urgency_level": "MODERATE",
        "urgency_label": "Cải thiện che chắn chuồng trại",
        "symptoms": [
            "Da vùng lưng và tai ửng đỏ, phù nề, heo tỏ ra đau rát khi chạm vào.",
            "Trường hợp nặng, lớp da cháy khô nứt nẻ và bong tróc từng mảng lớn.",
            "Thường gặp ở heo có sắc tố da trắng thả rông ngoài trời nắng gắt."
        ],
        "isolation_protocol": "Di dời heo vào chuồng có mái che mát ngay lập tức.",
        "disinfection": "Đảm bảo nguồn nước uống dồi dào, thông thoáng khí.",
        "treatment_protocol": [
            "Tưới tắm nước mát nhẹ nhàng hạ nhiệt cho heo.",
            "Bôi dầu khoáng làm mềm da hoặc kem làm mát chứa nha đam / Dexpanthenol.",
            "Tiêm giảm đau Flunixin meglumine hoặc Vitamin C liều cao nếu heo bị bỏng diện rộng."
        ]
    },
    "HEALTHY": {
        "code": "HEALTHY",
        "name_vi": "Heo khỏe mạnh (Bình thường)",
        "name_en": "Healthy Swine",
        "pathogen": "Không có mầm bệnh",
        "urgency_level": "SAFE",
        "urgency_label": "An toàn - Da bình thường",
        "symptoms": [
            "Làn da hồng hào, đàn hồi tốt, không có vết loét, nốt sần hay ban xuất huyết.",
            "Lông mượt, bóng, không rụng bất thường.",
            "Heo nhanh nhẹn, mắt sáng, ăn uống và vận động bình thường."
        ],
        "isolation_protocol": "Tiếp tục duy trì quy trình an toàn sinh học định kỳ.",
        "disinfection": "Phun sát trùng định kỳ 1-2 lần/tuần theo lịch chuẩn của trang trại.",
        "treatment_protocol": [
            "Duy trì chế độ dinh dưỡng đầy đủ vi khoáng và Vitamin.",
            "Thực hiện tiêm phòng vaccine đầy đủ theo đúng lịch tiêm của cơ quan thú y."
        ]
    }
}

# This is an educational first-response guide, not a prescription. Do not show
# drug names or doses as instructions without an examining veterinarian.
CARE_GUIDANCE = {
    "VIRA_FMD": {
        "care_summary": "Nghi lở mồm long móng cần được xem là tình huống khẩn cấp vì bệnh lây lan rất nhanh và phải được cơ quan thú y xác minh.",
        "treatment_protocol": [
            "Hạn chế người, phương tiện và động vật ra vào khu vực nghi nhiễm; không vận chuyển heo hoặc sản phẩm từ khu vực đó.",
            "Liên hệ ngay bác sĩ thú y hoặc cơ quan thú y địa phương để được hướng dẫn báo cáo, lấy mẫu và kiểm soát dịch.",
            "Không tự xử lý mụn nước hay dùng thuốc theo kết quả của mô hình. Chỉ vệ sinh, chăm sóc hỗ trợ theo hướng dẫn chuyên môn.",
        ],
        "source_urls": ["https://www.woah.org/en/disease/foot-and-mouth-disease/"],
    },
    "VIRA_POX": {
        "urgency_level": "MODERATE",
        "urgency_label": "Cần bác sĩ thú y đánh giá; kiểm soát côn trùng",
        "care_summary": "Đậu heo thường diễn tiến nhẹ, nhưng tổn thương dạng mụn nước cần được phân biệt với các bệnh truyền nhiễm nguy hiểm khác.",
        "treatment_protocol": [
            "Tách riêng heo có tổn thương khi có thể và hạn chế dùng chung dụng cụ chăm sóc.",
            "Trao đổi với bác sĩ thú y để xác nhận nguyên nhân, chăm sóc vết thương và kiểm soát chấy, rận hoặc côn trùng.",
            "Không tự dùng kháng sinh hoặc bôi hóa chất lên vùng da tổn thương.",
        ],
        "source_urls": ["https://www.merckvetmanual.com/integumentary-system/pox-diseases/swinepox"],
    },
    "BACT_ERY": {
        "care_summary": "Tổn thương đỏ tím dạng hình thoi có thể gặp ở bệnh đóng dấu lợn nhưng không đủ để tự xác nhận bệnh.",
        "treatment_protocol": [
            "Ghi lại thời điểm xuất hiện tổn thương và theo dõi tình trạng ăn uống, thân nhiệt, đi lại.",
            "Liên hệ bác sĩ thú y sớm để đánh giá và lựa chọn điều trị phù hợp; không tự dùng kháng sinh.",
            "Tăng cường vệ sinh, hạn chế tiếp xúc giữa heo nghi bệnh và đàn còn lại theo hướng dẫn của thú y.",
        ],
        "source_urls": ["https://www.merckvetmanual.com/infectious-diseases/erysipelothrix-rhusiopathiae-infection/swine-erysipelas"],
    },
    "BACT_GPD": {
        "care_summary": "Viêm da tiết dịch có thể gây tổn thương lan rộng, nhất là ở heo con; cần đánh giá nguyên nhân và mức độ mất nước.",
        "treatment_protocol": [
            "Giữ khu vực nằm sạch, khô và giảm cọ xát vào vùng da đang tổn thương.",
            "Nhờ bác sĩ thú y kiểm tra sớm để xác định nguyên nhân và lập kế hoạch chăm sóc, điều trị.",
            "Theo dõi khả năng uống nước, ăn và mức độ lan rộng; cần trợ giúp khẩn nếu heo yếu nhanh hoặc bỏ ăn.",
        ],
        "source_urls": ["https://www.merckvetmanual.com/integumentary-system/exudative-epidermitis/exudative-epidermitis-in-pigs"],
    },
    "FUNG_RING": {
        "care_summary": "Tổn thương dạng vòng có thể do nấm hoặc nguyên nhân khác; một số nấm da có thể lây sang người.",
        "treatment_protocol": [
            "Dùng găng khi chăm sóc vùng da tổn thương và rửa tay sau khi tiếp xúc.",
            "Hạn chế dùng chung bàn chải, khăn hoặc dụng cụ giữa các con; vệ sinh dụng cụ sau khi dùng.",
            "Nhờ bác sĩ thú y xác nhận nguyên nhân trước khi dùng thuốc bôi hoặc thuốc tắm.",
        ],
        "source_urls": ["https://www.merckvetmanual.com/integumentary-system/dermatophytosis/dermatophytosis-in-pigs%2C-sheep%2C-and-goats"],
    },
    "FUNG_ROSEA": {
        "urgency_level": "SAFE",
        "urgency_label": "Theo dõi; xác nhận nếu tổn thương lan rộng",
        "care_summary": "Một số tổn thương dạng vảy phấn hồng ở heo non có thể tự giới hạn; ảnh đơn lẻ không đủ xác nhận chẩn đoán.",
        "treatment_protocol": [
            "Theo dõi thay đổi kích thước, số lượng tổn thương và tình trạng toàn thân của heo.",
            "Giữ chuồng sạch, khô, giảm kích ứng da; hỏi bác sĩ thú y nếu tổn thương lan rộng hoặc heo có biểu hiện toàn thân.",
            "Không dùng thuốc điều trị nếu chưa được người có chuyên môn hướng dẫn.",
        ],
        "source_urls": ["https://www.merckvetmanual.com/integumentary-system/pityriasis-rosea-in-pigs/pityriasis-rosea-in-pigs"],
    },
    "PARA_MANGE": {
        "urgency_level": "MODERATE",
        "urgency_label": "Cần kiểm soát lây lan và được thú y đánh giá",
        "care_summary": "Ghẻ ở heo có thể lan nhanh khi tiếp xúc gần; xác nhận thường cần khám và có thể cần xét nghiệm da.",
        "treatment_protocol": [
            "Hạn chế tiếp xúc giữa heo nghi mắc ghẻ và nhóm khác; vệ sinh dụng cụ, khu vực nằm.",
            "Liên hệ bác sĩ thú y để chọn thuốc phù hợp cho cả nhóm tiếp xúc và kiểm tra thời gian ngưng thuốc.",
            "Không tự pha hoặc phun thuốc diệt ký sinh trùng lên heo; tuân thủ nhãn thuốc và hướng dẫn chuyên môn.",
        ],
        "source_urls": ["https://www.merckvetmanual.com/integumentary-system/mange/mange-in-pigs"],
    },
    "ENV_DERM": {
        "care_summary": "Viêm da tiếp xúc có thể liên quan đến nền chuồng, độ ẩm, hóa chất hoặc cọ xát; cần kiểm tra điều kiện nuôi.",
        "treatment_protocol": [
            "Kiểm tra khu vực nằm, thoát nước, độ ẩm và các hóa chất mới sử dụng trong chuồng.",
            "Giữ nền chuồng khô, giảm cọ xát và loại bỏ nguồn kích ứng rõ ràng nếu có thể thực hiện an toàn.",
            "Nhờ bác sĩ thú y đánh giá nếu da trợt loét, tiết dịch hoặc không cải thiện.",
        ],
        "source_urls": [""],
    },
    "ENV_SUN": {
        "care_summary": "Da heo có thể bị tổn thương do nắng hoặc nhiệt; cần đưa heo đến nơi râm mát và quan sát dấu hiệu sốc nhiệt.",
        "treatment_protocol": [
            "Đưa heo đến khu vực thoáng mát, có bóng râm và nước uống sạch.",
            "Tránh chườm lạnh đột ngột hoặc bôi sản phẩm không dành cho vật nuôi lên vùng da tổn thương.",
            "Gọi bác sĩ thú y nếu heo lờ đờ, thở bất thường, bỏ uống hoặc da phồng rộp trên diện rộng.",
        ],
        "source_urls": ["https://www.merckvetmanual.com/all-other-pets/potbellied-pigs/disorders-and-diseases-of-potbellied-pigs"],
    },
    "HEALTHY": {
        "care_summary": "Ảnh không cho thấy dấu hiệu bất thường rõ ràng theo mô hình. Điều này không loại trừ bệnh hoặc dấu hiệu ở vùng da ngoài khung hình.",
        "treatment_protocol": [
            "Tiếp tục quan sát da và hành vi ăn uống, vận động của heo.",
            "Duy trì vệ sinh chuồng trại và lịch chăm sóc, tiêm phòng do bác sĩ thú y xây dựng.",
            "Tìm hỗ trợ chuyên môn nếu xuất hiện tổn thương mới hoặc heo có biểu hiện bất thường.",
        ],
        "source_urls": [],
    },
}

for disease_code, guidance in CARE_GUIDANCE.items():
    DISEASES_DATA[disease_code].update(guidance)
