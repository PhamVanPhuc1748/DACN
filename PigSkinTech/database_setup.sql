-- =====================================================================================
-- PIGSKINTECH AI - ENTERPRISE SQL SERVER SCHEMA (CLEAN & HIGH-PERFORMANCE EDITION)
-- Database: PigSkinTechDB
-- Tương thích 100% với: services/store.py, chatbot_service.py, config_store.py
-- Hỗ trợ cả Fresh Install (Tạo mới) và Auto-Migration (Đồng bộ bảng có sẵn)
-- =====================================================================================

SET NOCOUNT ON;
GO

-- =====================================================================================
-- 1. KHỞI TẠO DATABASE & BẬT CHỐNG KHÓA BẢNG (READ_COMMITTED_SNAPSHOT)
-- =====================================================================================
IF DB_ID(N'PigSkinTechDB') IS NULL
BEGIN
    CREATE DATABASE PigSkinTechDB;
END
GO

USE PigSkinTechDB;
GO

IF (SELECT is_read_committed_snapshot_on FROM sys.databases WHERE name = N'PigSkinTechDB') = 0
BEGIN
    ALTER DATABASE PigSkinTechDB SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
END
GO

-- =====================================================================================
-- 2. BẢNG USERS: Quản lý Tài khoản, Phân quyền RBAC & Google OAuth 2.0
-- =====================================================================================
IF OBJECT_ID(N'dbo.Users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Users (
        id              INT IDENTITY(1,1) NOT NULL,
        email           VARCHAR(255)      NOT NULL,
        full_name       NVARCHAR(255)     NOT NULL,
        password_hash   VARCHAR(255)      NULL,
        role            VARCHAR(30)       NOT NULL CONSTRAINT DF_Users_Role DEFAULT ('user'),
        auth_provider   VARCHAR(30)       NOT NULL CONSTRAINT DF_Users_Provider DEFAULT ('local'),
        google_sub      VARCHAR(255)      NULL,
        avatar_url      NVARCHAR(500)     NULL,
        phone           VARCHAR(30)       NULL,
        farm_name       NVARCHAR(255)     NULL,
        is_active       BIT               NOT NULL CONSTRAINT DF_Users_Active DEFAULT (1),
        created_at      DATETIME2(0)      NOT NULL CONSTRAINT DF_Users_Created DEFAULT (SYSDATETIME()),
        updated_at      DATETIME2(0)      NULL,

        CONSTRAINT PK_Users PRIMARY KEY CLUSTERED (id ASC),
        CONSTRAINT UQ_Users_Email UNIQUE NONCLUSTERED (email ASC),
        CONSTRAINT CK_Users_Role CHECK (role IN ('user', 'expert', 'admin'))
    );
END
ELSE
BEGIN
    IF COL_LENGTH(N'dbo.Users', N'full_name') IS NULL
        ALTER TABLE dbo.Users ADD full_name NVARCHAR(255) NOT NULL CONSTRAINT DF_Users_FullName_Mig DEFAULT (N'Người dùng');
    IF COL_LENGTH(N'dbo.Users', N'password_hash') IS NULL
        ALTER TABLE dbo.Users ADD password_hash VARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Users', N'role') IS NULL
        ALTER TABLE dbo.Users ADD role VARCHAR(30) NOT NULL CONSTRAINT DF_Users_Role_Mig DEFAULT ('user');
    IF COL_LENGTH(N'dbo.Users', N'auth_provider') IS NULL
        ALTER TABLE dbo.Users ADD auth_provider VARCHAR(30) NOT NULL CONSTRAINT DF_Users_Prov_Mig DEFAULT ('local');
    IF COL_LENGTH(N'dbo.Users', N'google_sub') IS NULL
        ALTER TABLE dbo.Users ADD google_sub VARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Users', N'avatar_url') IS NULL
        ALTER TABLE dbo.Users ADD avatar_url NVARCHAR(500) NULL;
    IF COL_LENGTH(N'dbo.Users', N'phone') IS NULL
        ALTER TABLE dbo.Users ADD phone VARCHAR(30) NULL;
    IF COL_LENGTH(N'dbo.Users', N'farm_name') IS NULL
        ALTER TABLE dbo.Users ADD farm_name NVARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Users', N'is_active') IS NULL
        ALTER TABLE dbo.Users ADD is_active BIT NOT NULL CONSTRAINT DF_Users_Act_Mig DEFAULT (1);
    IF COL_LENGTH(N'dbo.Users', N'created_at') IS NULL
        ALTER TABLE dbo.Users ADD created_at DATETIME2(0) NOT NULL CONSTRAINT DF_Users_Cat_Mig DEFAULT (SYSDATETIME());
    IF COL_LENGTH(N'dbo.Users', N'updated_at') IS NULL
        ALTER TABLE dbo.Users ADD updated_at DATETIME2(0) NULL;
END
GO

-- =====================================================================================
-- 3. BẢNG DISEASE_CATALOG: Danh mục 10 Nhóm Bệnh lý & Phác đồ Điều trị Chuẩn
-- =====================================================================================
IF OBJECT_ID(N'dbo.DiseaseCatalog', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.DiseaseCatalog (
        id                  INT IDENTITY(1,1) NOT NULL,
        class_key           VARCHAR(120)      NOT NULL,
        display_name        NVARCHAR(255)     NOT NULL,
        danger_level        NVARCHAR(30)      NOT NULL CONSTRAINT DF_Disease_Danger DEFAULT (N'Trung bình'),
        symptoms            NVARCHAR(MAX)     NULL,
        prevention          NVARCHAR(MAX)     NULL,
        treatment_protocol  NVARCHAR(MAX)     NULL,
        is_active           BIT               NOT NULL CONSTRAINT DF_Disease_Active DEFAULT (1),
        updated_by          NVARCHAR(255)     NULL,
        updated_at          DATETIME2(0)      NOT NULL CONSTRAINT DF_Disease_Updated DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_DiseaseCatalog PRIMARY KEY CLUSTERED (id ASC),
        CONSTRAINT UQ_DiseaseCatalog_ClassKey UNIQUE NONCLUSTERED (class_key ASC)
    );
END
ELSE
BEGIN
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'class_key') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD class_key VARCHAR(120) NULL;
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'display_name') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD display_name NVARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'danger_level') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD danger_level NVARCHAR(30) NOT NULL CONSTRAINT DF_Dis_Danger_Mig DEFAULT (N'Trung bình');
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'symptoms') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD symptoms NVARCHAR(MAX) NULL;
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'prevention') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD prevention NVARCHAR(MAX) NULL;
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'treatment_protocol') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD treatment_protocol NVARCHAR(MAX) NULL;
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'is_active') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD is_active BIT NOT NULL CONSTRAINT DF_Dis_Active_Mig DEFAULT (1);
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'updated_by') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD updated_by NVARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.DiseaseCatalog', N'updated_at') IS NULL
        ALTER TABLE dbo.DiseaseCatalog ADD updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_Dis_Upd_Mig DEFAULT (SYSDATETIME());
END
GO

-- =====================================================================================
-- 4. BẢNG INSPECTIONS: Hồ sơ Chẩn đoán Bệnh từ Model Thật & Thẩm định Chuyên gia
-- =====================================================================================
IF OBJECT_ID(N'dbo.Seq_CaseId', N'SO') IS NULL
BEGIN
    CREATE SEQUENCE dbo.Seq_CaseId AS INT START WITH 1 INCREMENT BY 1;
END
GO

IF OBJECT_ID(N'dbo.Inspections', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Inspections (
        id                  INT IDENTITY(1,1) NOT NULL,
        case_id             VARCHAR(50)       NOT NULL CONSTRAINT DF_Inspections_CaseId 
                                              DEFAULT ('PS-' + RIGHT('000000' + CAST(NEXT VALUE FOR dbo.Seq_CaseId AS VARCHAR(10)), 6)),
        user_id             INT               NULL,
        user_email          VARCHAR(255)      NULL,
        user_name           NVARCHAR(255)     NULL,
        animal_id           VARCHAR(100)      NULL,
        farm_name           NVARCHAR(255)     NULL,
        symptoms            NVARCHAR(MAX)     NULL,
        image_path          NVARCHAR(500)     NOT NULL,
        model_name          VARCHAR(150)      NOT NULL,
        predicted_class     VARCHAR(120)      NOT NULL,
        predicted_label     NVARCHAR(255)     NULL,
        confidence          FLOAT             NOT NULL CONSTRAINT DF_Inspections_Conf DEFAULT (0.0),
        inference_ms        FLOAT             NULL     CONSTRAINT DF_Inspections_Ms DEFAULT (0.0),
        top3_scores_json    NVARCHAR(MAX)     NULL,
        danger_level        NVARCHAR(30)      NULL,
        recommendation      NVARCHAR(MAX)     NULL,
        requested_review    BIT               NOT NULL CONSTRAINT DF_Inspections_ReqRev DEFAULT (0),
        review_status       VARCHAR(30)       NOT NULL CONSTRAINT DF_Inspections_RevStatus DEFAULT ('pending'),
        agreed_with_ai      BIT               NULL,
        expert_label        VARCHAR(120)      NULL,
        expert_display_name NVARCHAR(255)     NULL,
        expert_note         NVARCHAR(MAX)     NULL,
        reviewed_by         NVARCHAR(255)     NULL,
        reviewed_at         DATETIME2(0)      NULL,
        in_dataset          BIT               NOT NULL CONSTRAINT DF_Inspections_InDataset DEFAULT (0),
        created_at          DATETIME2(0)      NOT NULL CONSTRAINT DF_Inspections_Created DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_Inspections PRIMARY KEY CLUSTERED (id ASC),
        CONSTRAINT UQ_Inspections_CaseId UNIQUE NONCLUSTERED (case_id ASC),
        CONSTRAINT FK_Inspections_Users FOREIGN KEY (user_id) REFERENCES dbo.Users(id) ON DELETE SET NULL
    );
END
ELSE
BEGIN
    IF COLUMNPROPERTY(OBJECT_ID(N'dbo.Inspections'), N'case_id', 'IsComputed') = 1
        ALTER TABLE dbo.Inspections DROP COLUMN case_id;

    IF COL_LENGTH(N'dbo.Inspections', N'case_id') IS NULL
        ALTER TABLE dbo.Inspections ADD case_id VARCHAR(50) NOT NULL 
            CONSTRAINT DF_Inspections_CaseId_Mig DEFAULT ('PS-' + RIGHT('000000' + CAST(NEXT VALUE FOR dbo.Seq_CaseId AS VARCHAR(10)), 6));
    IF COL_LENGTH(N'dbo.Inspections', N'user_id') IS NULL
        ALTER TABLE dbo.Inspections ADD user_id INT NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'user_email') IS NULL
        ALTER TABLE dbo.Inspections ADD user_email VARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'user_name') IS NULL
        ALTER TABLE dbo.Inspections ADD user_name NVARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'animal_id') IS NULL
        ALTER TABLE dbo.Inspections ADD animal_id VARCHAR(100) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'farm_name') IS NULL
        ALTER TABLE dbo.Inspections ADD farm_name NVARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'symptoms') IS NULL
        ALTER TABLE dbo.Inspections ADD symptoms NVARCHAR(MAX) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'image_path') IS NULL
        ALTER TABLE dbo.Inspections ADD image_path NVARCHAR(500) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'model_name') IS NULL
        ALTER TABLE dbo.Inspections ADD model_name VARCHAR(150) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'predicted_class') IS NULL
        ALTER TABLE dbo.Inspections ADD predicted_class VARCHAR(120) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'predicted_label') IS NULL
        ALTER TABLE dbo.Inspections ADD predicted_label NVARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'confidence') IS NULL
        ALTER TABLE dbo.Inspections ADD confidence FLOAT NOT NULL CONSTRAINT DF_Insp_Conf_Mig DEFAULT (0.0);
    IF COL_LENGTH(N'dbo.Inspections', N'inference_ms') IS NULL
        ALTER TABLE dbo.Inspections ADD inference_ms FLOAT NULL CONSTRAINT DF_Insp_Ms_Mig DEFAULT (0.0);
    IF COL_LENGTH(N'dbo.Inspections', N'top3_scores_json') IS NULL
        ALTER TABLE dbo.Inspections ADD top3_scores_json NVARCHAR(MAX) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'danger_level') IS NULL
        ALTER TABLE dbo.Inspections ADD danger_level NVARCHAR(30) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'recommendation') IS NULL
        ALTER TABLE dbo.Inspections ADD recommendation NVARCHAR(MAX) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'requested_review') IS NULL
        ALTER TABLE dbo.Inspections ADD requested_review BIT NOT NULL CONSTRAINT DF_Insp_Req_Mig DEFAULT (0);
    IF COL_LENGTH(N'dbo.Inspections', N'review_status') IS NULL
        ALTER TABLE dbo.Inspections ADD review_status VARCHAR(30) NOT NULL CONSTRAINT DF_Insp_Stat_Mig DEFAULT ('pending');
    IF COL_LENGTH(N'dbo.Inspections', N'agreed_with_ai') IS NULL
        ALTER TABLE dbo.Inspections ADD agreed_with_ai BIT NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'expert_label') IS NULL
        ALTER TABLE dbo.Inspections ADD expert_label VARCHAR(120) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'expert_display_name') IS NULL
        ALTER TABLE dbo.Inspections ADD expert_display_name NVARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'expert_note') IS NULL
        ALTER TABLE dbo.Inspections ADD expert_note NVARCHAR(MAX) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'reviewed_by') IS NULL
        ALTER TABLE dbo.Inspections ADD reviewed_by NVARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'reviewed_at') IS NULL
        ALTER TABLE dbo.Inspections ADD reviewed_at DATETIME2(0) NULL;
    IF COL_LENGTH(N'dbo.Inspections', N'in_dataset') IS NULL
        ALTER TABLE dbo.Inspections ADD in_dataset BIT NOT NULL CONSTRAINT DF_Insp_Data_Mig DEFAULT (0);
    IF COL_LENGTH(N'dbo.Inspections', N'created_at') IS NULL
        ALTER TABLE dbo.Inspections ADD created_at DATETIME2(0) NOT NULL CONSTRAINT DF_Insp_Cat_Mig DEFAULT (SYSDATETIME());
END
GO

-- =====================================================================================
-- 5. BẢNG CHAT_MESSAGES: Lưu đồng bộ 100% Lịch sử Trợ lý AI Thú y (Tab & Popup)
-- =====================================================================================
IF OBJECT_ID(N'dbo.ChatMessages', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ChatMessages (
        id              INT IDENTITY(1,1) NOT NULL,
        user_id         INT               NULL,
        user_email      VARCHAR(255)      NULL,
        inspection_id   INT               NULL,
        case_id         VARCHAR(50)       NULL,
        sender          VARCHAR(20)       NOT NULL CONSTRAINT DF_Chat_Sender DEFAULT ('user'),
        message_text    NVARCHAR(MAX)     NOT NULL,
        created_at      DATETIME2(0)      NOT NULL CONSTRAINT DF_Chat_Created DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_ChatMessages PRIMARY KEY CLUSTERED (id ASC),
        CONSTRAINT FK_ChatMessages_Users FOREIGN KEY (user_id) REFERENCES dbo.Users(id) ON DELETE SET NULL
    );
END
ELSE
BEGIN
    IF COL_LENGTH(N'dbo.ChatMessages', N'user_id') IS NULL
        ALTER TABLE dbo.ChatMessages ADD user_id INT NULL;
    IF COL_LENGTH(N'dbo.ChatMessages', N'user_email') IS NULL
        ALTER TABLE dbo.ChatMessages ADD user_email VARCHAR(255) NULL;
    IF COL_LENGTH(N'dbo.ChatMessages', N'inspection_id') IS NULL
        ALTER TABLE dbo.ChatMessages ADD inspection_id INT NULL;
    IF COL_LENGTH(N'dbo.ChatMessages', N'case_id') IS NULL
        ALTER TABLE dbo.ChatMessages ADD case_id VARCHAR(50) NULL;
    IF COL_LENGTH(N'dbo.ChatMessages', N'sender') IS NULL
        ALTER TABLE dbo.ChatMessages ADD sender VARCHAR(20) NOT NULL CONSTRAINT DF_Chat_Sender_Mig DEFAULT ('user');
    IF COL_LENGTH(N'dbo.ChatMessages', N'message_text') IS NULL
        ALTER TABLE dbo.ChatMessages ADD message_text NVARCHAR(MAX) NULL;
    IF COL_LENGTH(N'dbo.ChatMessages', N'created_at') IS NULL
        ALTER TABLE dbo.ChatMessages ADD created_at DATETIME2(0) NOT NULL CONSTRAINT DF_Chat_Cat_Mig DEFAULT (SYSDATETIME());
END
GO

-- =====================================================================================
-- 6. BẢNG MODEL_VERSIONS: Quản lý Trọng số AI (.pt)
-- =====================================================================================
IF OBJECT_ID(N'dbo.ModelVersions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ModelVersions (
        id              INT IDENTITY(1,1) NOT NULL,
        version_name    NVARCHAR(200)     NOT NULL,
        architecture    VARCHAR(100)      NOT NULL,
        weights_path    NVARCHAR(500)     NOT NULL,
        accuracy        FLOAT             NULL,
        is_active       BIT               NOT NULL CONSTRAINT DF_Model_Active DEFAULT (0),
        activated_by    NVARCHAR(255)     NULL,
        activated_at    DATETIME2(0)      NOT NULL CONSTRAINT DF_Model_ActTime DEFAULT (SYSDATETIME()),

        CONSTRAINT PK_ModelVersions PRIMARY KEY CLUSTERED (id ASC),
        CONSTRAINT UQ_ModelVersions_Path UNIQUE NONCLUSTERED (weights_path ASC)
    );
END
GO

-- =====================================================================================
-- 7. HỆ THỐNG COVERING INDEXES (TỐI ƯU TỐC ĐỘ TRUY VẤN < 2ms)
--    Sử dụng sp_executesql để tương thích tuyệt đối sau khi ALTER TABLE
-- =====================================================================================
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Inspections_ExpertQueue' AND object_id = OBJECT_ID(N'dbo.Inspections'))
BEGIN
    EXEC sp_executesql N'
    CREATE NONCLUSTERED INDEX IX_Inspections_ExpertQueue
    ON dbo.Inspections (requested_review ASC, review_status ASC, created_at DESC)
    INCLUDE (case_id, animal_id, farm_name, predicted_class, predicted_label, confidence, image_path, user_name, user_email);';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Inspections_UserHistory' AND object_id = OBJECT_ID(N'dbo.Inspections'))
BEGIN
    EXEC sp_executesql N'
    CREATE NONCLUSTERED INDEX IX_Inspections_UserHistory
    ON dbo.Inspections (user_email ASC, created_at DESC)
    INCLUDE (case_id, animal_id, predicted_class, predicted_label, confidence, review_status, expert_label, in_dataset);';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Inspections_Analytics' AND object_id = OBJECT_ID(N'dbo.Inspections'))
BEGIN
    EXEC sp_executesql N'
    CREATE NONCLUSTERED INDEX IX_Inspections_Analytics
    ON dbo.Inspections (predicted_class ASC, danger_level ASC, review_status ASC)
    INCLUDE (confidence, agreed_with_ai, in_dataset, created_at);';
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_ChatMessages_UserFast' AND object_id = OBJECT_ID(N'dbo.ChatMessages'))
BEGIN
    EXEC sp_executesql N'
    CREATE NONCLUSTERED INDEX IX_ChatMessages_UserFast
    ON dbo.ChatMessages (user_email ASC, id ASC)
    INCLUDE (sender, created_at);';
END
GO

-- =====================================================================================
-- 8. SQL VIEW TÍNH SẴN SỐ LIỆU KPI & BIỂU ĐỒ (TRUY VẤN 1 LỆNH DUY NHẤT)
-- =====================================================================================
CREATE OR ALTER VIEW dbo.vw_DashboardKPIs
AS
SELECT
    (SELECT COUNT(1) FROM dbo.Users WHERE is_active = 1) AS total_users,
    COUNT(1) AS total_inspections,
    ISNULL(SUM(CASE WHEN requested_review = 1 AND review_status = 'pending' THEN 1 ELSE 0 END), 0) AS pending_reviews,
    ISNULL(SUM(CASE WHEN review_status = 'reviewed' THEN 1 ELSE 0 END), 0) AS reviewed_count,
    ISNULL(SUM(CASE WHEN review_status = 'reviewed' AND agreed_with_ai = 1 THEN 1 ELSE 0 END), 0) AS agreed_count,
    CAST(
        CASE 
            WHEN SUM(CASE WHEN review_status = 'reviewed' THEN 1 ELSE 0 END) > 0 
            THEN (SUM(CASE WHEN review_status = 'reviewed' AND agreed_with_ai = 1 THEN 1.0 ELSE 0.0 END) * 100.0) 
                 / SUM(CASE WHEN review_status = 'reviewed' THEN 1.0 ELSE 0.0 END)
            ELSE 0.0 
        END AS DECIMAL(5,1)
    ) AS ai_agreement_rate,
    ISNULL(SUM(CASE WHEN in_dataset = 1 THEN 1 ELSE 0 END), 0) AS dataset_count
FROM dbo.Inspections;
GO

-- =====================================================================================
-- 9. SEED DATA CHUẨN (3 TÀI KHOẢN MẶC ĐỊNH & 10 NHÓM BỆNH LÝ TỪ CLASSES.JSON)
-- =====================================================================================
EXEC sp_executesql N'
MERGE INTO dbo.Users AS target
USING (VALUES
    (''admin.pigskin@gmail.com'',   N''Quản trị viên PigSkinTech'', ''8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92'', ''admin'',  ''local''),
    (''bs.thuy.pigskin@gmail.com'', N''BS. Trần Thị Thúy (Thú y)'', ''8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92'', ''expert'', ''local''),
    (''nongdan.pigskin@gmail.com'', N''Nguyễn Văn Nông (Chủ trại)'',''8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92'', ''user'',   ''local'')
) AS src (email, full_name, password_hash, role, auth_provider)
ON target.email = src.email
WHEN NOT MATCHED THEN
    INSERT (email, full_name, password_hash, role, auth_provider, is_active)
    VALUES (src.email, src.full_name, src.password_hash, src.role, src.auth_provider, 1);
';
GO

EXEC sp_executesql N'
MERGE INTO dbo.DiseaseCatalog AS target
USING (VALUES
    (''Healthy'', N''Da khỏe mạnh (Bình thường)'', N''An toàn'',
     N''Da hồng hào, lông bóng mượt, không có vết loét, mụn mủ, đóng vảy hay mảng xuất huyết.'',
     N''Duy trì vệ sinh chuồng trại khô thoáng, tiêm phòng đầy đủ vắc-xin định kỳ và bổ sung khoáng chất, vitamin.'',
     N''Không cần điều trị thuốc. Tiếp tục theo dõi định kỳ và đảm bảo khẩu phần dinh dưỡng.''),

    (''Infected_Bacterial_Erysipelas'', N''Bệnh đóng dấu lợn (Erysipelas)'', N''Cao'',
     N''Sốt cao 41-42°C, xuất hiện các mảng đỏ hình thoi/vuông nổi cộm trên da lưng, ngực, cổ; ấn vào mất màu rồi đỏ lại.'',
     N''Tiêm vắc-xin phòng bệnh đóng dấu heo định kỳ 6 tháng/lần, cách ly ngay cá thể sốt và phun sát trùng chuồng nuôi.'',
     N''Tiêm Penicillin G (20.000-30.000 IU/kg TT) hoặc Amoxicillin LA kết hợp hạ sốt Analgin + Vitamin C trong 3-5 ngày.''),

    (''Infected_Bacterial_Greasy_Pig_Disease'', N''Viêm da tiết dịch (Greasy Pig Disease)'', N''Cao'',
     N''Da tiết dịch nhờn màu nâu đen có mùi hôi, đóng vảy dày nứt nẻ quanh mặt, cổ và lan toàn thân do Staphylococcus hyicus.'',
     N''Bấm nanh heo con đúng kỹ thuật, sát trùng rốn và vết trầy xước, giữ chuồng đẻ sạch và khô.'',
     N''Tắm rửa vùng da bằng dung dịch Iodine 1% hoặc Chlorhexidine, tiêm Amoxicillin/Lincomycin và bù điện giải.''),

    (''Infected_Environmental_Dermatitis'', N''Viêm da do môi trường (Dermatitis)'', N''Trung bình'',
     N''Da đỏ, sần sùi, trầy xước hoặc kích ứng cục bộ vùng bụng, đùi do nền chuồng ẩm ướt, khí NH3 cao hoặc hóa chất.'',
     N''Cải thiện thông gió, giảm độ ẩm nền chuồng, dọn phân nước tiểu hàng ngày và tránh dùng hóa chất tẩy rửa quá đặc.'',
     N''Chuyển sang ô chuồng khô sạch, xịt dung dịch sát khuẩn dịu nhẹ (Povidone-Iodine) và bổ sung Kẽm + Biotin.''),

    (''Infected_Environmental_Sunburn'', N''Cháy nắng da heo (Sunburn)'', N''Thấp'',
     N''Da vùng lưng, tai đỏ rát, phồng rộp nhẹ hoặc bong tróc vảy trắng sau khi tiếp xúc ánh nắng gắt kéo dài.'',
     N''Che lưới lan chống nắng khu vực sân chơi, cung cấp đủ nước uống mát và bùn/nước làm mát.'',
     N''Đưa heo vào khu vực râm mát, bôi kem làm dịu chứa kẽm oxit/panthenol và cung cấp đủ nước mát pha điện giải.''),

    (''Infected_Fungal_Pityriasis_Rosea'', N''Bệnh vảy phấn hồng (Pityriasis Rosea)'', N''Thấp'',
     N''Tổn thương hình vòng tròn hoặc bầu dục màu đỏ hồng có viền vảy trắng mịn ở vùng bụng và mặt trong đùi heo con.'',
     N''Giữ vệ sinh chuồng cai sữa khô ráo, giảm mật độ nuôi và chọn lọc giống vì bệnh có yếu tố di truyền.'',
     N''Bệnh thường tự khỏi sau 4-8 tuần; vệ sinh da bằng dung dịch sát khuẩn nhẹ để tránh nhiễm trùng kế phát.''),

    (''Infected_Fungal_Ringworm'', N''Bệnh nấm da / Hắc lào (Ringworm)'', N''Trung bình'',
     N''Các mảng tròn rụng lông, bề mặt phủ lớp vảy xám trắng khô ráp ở cổ, lưng, hông do nấm Microsporum/Trichophyton.'',
     N''Khử trùng chuồng trại, dụng cụ chăn nuôi, diệt chuột và tránh để chuồng ẩm thấp thiếu ánh sáng.'',
     N''Bôi cồn Iodine 2-5% hoặc thuốc mỡ kháng nấm (Ketoconazole/Miconazole) ngày 1-2 lần kết hợp bổ sung Vitamin A, Kẽm.''),

    (''Infected_Parasitic_Mange'', N''Bệnh ghẻ Sarcoptes (Mange)'', N''Cao'',
     N''Heo ngứa gãi dữ dội cọ vào thành chuồng, da dày sừng đóng vảy sần sùi ở vành tai, cổ, mông; rụng lông.'',
     N''Tẩy ghẻ định kỳ cho đàn nái trước khi đẻ và heo mới nhập trại, phun thuốc diệt cái ghẻ lên nền và vách chuồng.'',
     N''Tiêm dưới da Ivermectin hoặc Doramectin (1 ml/33 kg TT), lặp lại mũi thứ 2 sau 10-14 ngày kết hợp phun Amitraz chuồng nuôi.''),

    (''Infected_Viral_Foot_And_Mouth'', N''Lở mồm long móng (FMD)'', N''Cao'',
     N''Sốt cao, nổi mụn nước ở gương mũi, vành móng, kẽ chân và vú; mụn vỡ tạo vết loét đỏ khiến heo đi khập khiễng, bỏ ăn.'',
     N''Tiêm vắc-xin LMLM định kỳ, kiểm dịch nghiêm ngặt người và phương tiện ra vào trại, rắc vôi bột lối đi.'',
     N''Cách ly khẩn cấp toàn bộ ô chuồng, báo cơ quan thú y địa phương, rửa vết loét bằng Xanh Methylen/Iodine và chống phụ nhiễm.''),

    (''Infected_Viral_Swinepox'', N''Bệnh đậu heo (Swinepox)'', N''Trung bình'',
     N''Xuất hiện nốt sẩn đỏ chuyển thành mụn nước, mụn mủ rồi đóng vảy nâu đen tròn ở vùng bụng, bẹn, tai và mặt.'',
     N''Diệt rận heo, ruồi muỗi (vật chủ trung gian truyền virus đậu), sát trùng chuồng trại định kỳ.'',
     N''Bôi Xanh Methylen 1% hoặc Iodine lên các nốt đậu vỡ để chống nhiễm khuẩn kế phát, bổ sung Vitamin C và gluco-K-C.'')
) AS src (class_key, display_name, danger_level, symptoms, prevention, treatment_protocol)
ON target.class_key = src.class_key
WHEN MATCHED THEN
    UPDATE SET
        display_name = src.display_name,
        danger_level = src.danger_level,
        symptoms = src.symptoms,
        prevention = src.prevention,
        treatment_protocol = src.treatment_protocol,
        updated_at = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (class_key, display_name, danger_level, symptoms, prevention, treatment_protocol)
    VALUES (src.class_key, src.display_name, src.danger_level, src.symptoms, src.prevention, src.treatment_protocol);
';
GO

-- Kiểm tra trạng thái sạch sẽ và tốc độ phản hồi của View KPI
SELECT * FROM dbo.vw_DashboardKPIs;
GO