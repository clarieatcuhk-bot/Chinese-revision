from db_core import get_supabase
from ai_engine import get_clean_category

def run_hot_migrate():
    supabase = get_supabase()
    
    # 1. shared_questions
    print("Migrating shared_questions...")
    res = supabase.table("shared_questions").select("*").execute()
    for row in res.data:
        full_text = str(row.get("question", "")) + " " + str(row.get("analysis", ""))
        old_cat = row.get("category", "")
        if old_cat.startswith("DRAFT_"): continue # Draft handled by clean_draft_pool_data
        
        clean = get_clean_category(old_cat, full_text)
        if old_cat != clean:
            print(f"Updating shared_questions {row['id']}: {old_cat} -> {clean}")
            supabase.table("shared_questions").update({"category": clean}).eq("id", row['id']).execute()
            
    # 2. answer_logs
    print("Migrating answer_logs...")
    res2 = supabase.table("answer_logs").select("*").execute()
    for row in res2.data:
        full_text = str(row.get("question", "")) + " " + str(row.get("analysis", ""))
        old_cat = row.get("category", "")
        clean = get_clean_category(old_cat, full_text)
        if old_cat != clean:
            print(f"Updating answer_logs {row['id']}: {old_cat} -> {clean}")
            supabase.table("answer_logs").update({"category": clean}).eq("id", row['id']).execute()
            
    print("Migration complete!")

if __name__ == "__main__":
    run_hot_migrate()
