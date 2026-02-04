import time
import datetime
from pymongo import MongoClient
import urllib.parse

# ================= 配置区 =================
# 对密码进行 URL 编码，防止 # 等特殊字符导致连接失败
username = urllib.parse.quote_plus("ubiwell_root")
password = urllib.parse.quote_plus("UbiwellAdmin#2026")
host = "127.0.0.1"
port = "27017"
auth_db = "admin" # 用户是在这个库创建的

# 拼接连接字符串
MONGO_URI = f"mongodb://{username}:{password}@{host}:{port}/{auth_db}?authSource={auth_db}"

# 目标数据库和ID
DB_NAME = "study_db"
PARTICIPANT_ID = "test002" # 你的测试 ID
# =========================================

def debug_query():
    client = None
    try:
        print(f"--- 正在连接 MongoDB ({host}:{port}) ---")
        client = MongoClient(MONGO_URI)
        
        # 测试连接是否成功
        client.admin.command('ping')
        print("✅ 连接成功！")

        db = client[DB_NAME]
        
        # 你的集合名，通常是 garmin_hr
        COLLECTION_NAME = "garmin_hr"
        collection = db[COLLECTION_NAME]

        print(f"\n--- 开始诊断 ID: {PARTICIPANT_ID} 在表 '{COLLECTION_NAME}' ---")

        # 1. 裸查：完全不带时间条件，只查 ID
        print("\n步骤 1: 检查 ID 字段名...")
        
        # 尝试匹配 'uid'
        doc_uid = collection.find_one({"uid": PARTICIPANT_ID})
        
        sample_doc = None
        if doc_uid:
            print(f"✅ 成功通过 'uid' 字段找到记录！")
            sample_doc = doc_uid
        else:
            print("❌ 未能通过 'uid' 找到记录。尝试 'participant_id'...")
            doc_pid = collection.find_one({"participant_id": PARTICIPANT_ID})
            if doc_pid:
                print(f"✅ 成功通过 'participant_id' 字段找到记录！(你的代码里写的是 uid，需要改成 participant_id)")
                sample_doc = doc_pid
            else:
                print("❌ 也没找到。该用户在表里完全没数据，或者 ID 错了。")
                print(f"   (正在检查的 ID 是: {PARTICIPANT_ID})")
                return

        # 2. 检查时间字段和格式
        print("\n步骤 2: 检查时间格式...")
        
        # 打印所有键，方便你确认字段名
        print(f"文档的所有字段: {list(sample_doc.keys())}")

        time_field = "startTimeInSeconds"
        time_val = sample_doc.get(time_field)
        
        if time_val is None:
            time_field = "timestamp"
            time_val = sample_doc.get(time_field)
        
        if time_val is None:
            print("❌ 找不到常见的时间字段 (startTimeInSeconds 或 timestamp)。")
            return

        print(f"找到时间字段: '{time_field}', 样本值: {time_val}")
        
        is_millis = time_val > 1000000000000 # 如果大于 13 位数大概率是毫秒
        time_unit = '毫秒 (ms)' if is_millis else '秒 (s)'
        print(f"推测时间单位: {time_unit}")

        # 3. 模拟 24h 查询
        print("\n步骤 3: 模拟 24h 查询窗口...")
        
        now = datetime.datetime.utcnow()
        end_dt = now
        start_dt = now - datetime.timedelta(hours=24)
        
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        # 修正单位
        if is_millis:
            start_ts *= 1000
            end_ts *= 1000

        print(f"查询时间范围 ({time_unit}): {start_ts} -> {end_ts}")

        query = {
            "uid": PARTICIPANT_ID, 
            time_field: {"$gte": start_ts, "$lte": end_ts}
        }
        
        count = collection.count_documents(query)
        print(f"📊 在过去 24 小时内找到 {count} 条数据")

        if count == 0:
            print("⚠️ 结论: 最近24小时没数据。")
            
            # 查一下该用户最新一条数据是什么时候
            latest = collection.find_one({"uid": PARTICIPANT_ID}, sort=[(time_field, -1)])
            if latest:
                latest_time = latest.get(time_field)
                # 转换成人读得懂的时间
                ts_for_date = latest_time / 1000 if is_millis else latest_time
                readable_time = datetime.datetime.fromtimestamp(ts_for_date)
                print(f"ℹ️ 该用户最近一条数据时间是: {readable_time} (UTC)")
                print("   如果这个时间是很久以前，说明 Range 设为 24h 查不到是正常的。")

    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        if client:
            client.close()

if __name__ == "__main__":
    debug_query()