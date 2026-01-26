#!/usr/bin/env python3
"""
OpenCode Infinity Lite - 精簡版（功能對等 hardcode 版本）
核心功能：自動執行 + 指數退避重試 + Token 監控 + 上下文傳遞
"""
import subprocess
import sys
import time
import json
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("錯誤：pip3 install pyyaml")

# ==================== 顏色輸出 ====================
class C:
    R = '\033[0m'
    B = '\033[94m'  # 藍
    G = '\033[92m'  # 綠
    Y = '\033[93m'  # 黃
    E = '\033[91m'  # 紅
    COLORS = ['\033[96m', '\033[95m', '\033[92m', '\033[93m', '\033[91m', '\033[94m']  # 6色輪轉

def log(msg): print(f"{C.B}[腳本] {msg}{C.R}")
def ok(msg): print(f"{C.G}✓ {msg}{C.R}")
def warn(msg): print(f"{C.Y}⚠ {msg}{C.R}")
def err(msg): print(f"{C.E}✗ {msg}{C.R}")
def sep(char="═"): print(char * 70)

# ==================== 工具函數 ====================
def load_config(config_name='medical-kb'):
    """載入配置"""
    config_file = Path(f'tasks_yaml/{config_name}.yaml')
    if config_file.exists():
        with open(config_file) as f:
            cfg = yaml.safe_load(f)
            ok(f"已加載配置: {config_name}.yaml")
            if 'task' in cfg and 'output_dir' in cfg['task']:
                print(f"  輸出目錄: {cfg['task']['output_dir']}/\n")
            return cfg
    
    warn(f"配置文件不存在: {config_file}")
    return {
        'task': {'name': '通用任務', 'language': '繁體中文'},
        'opencode': {'max_tokens': 128000, 'token_threshold': 0.7},
        'execution': {'delay': 1, 'timeout': 300, 'max_retries': 5},
        'prompts': ['繼續工作'],
        'summary_prompt': '總結本輪工作（300字內）'
    }

def get_tokens(session_id):
    """獲取 session 的 token 使用量（累加所有 output）"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tmp = f.name
        subprocess.run(['opencode', 'export', session_id], stdout=open(tmp, 'w'), 
                      stderr=subprocess.DEVNULL, timeout=10)
        with open(tmp) as f:
            content = f.read()
            data = json.loads(content[content.find('{'):])
        Path(tmp).unlink()
        
        # 累加所有 output tokens（AI 的回應會累積到 context）
        total_output = 0
        for msg in data.get('messages', []):
            for part in msg.get('parts', []) if isinstance(msg, dict) else []:
                if isinstance(part, dict) and part.get('type') == 'step-finish':
                    total_output += part.get('tokens', {}).get('output', 0)
        return total_output
    except:
        return None

def get_title(session_id):
    """獲取 session 標題"""
    try:
        result = subprocess.run(['opencode', 'session', 'list'], 
                              capture_output=True, text=True, timeout=5)
        for line in result.stdout.split('\n'):
            if line.startswith(session_id):
                parts = line.split(maxsplit=2)
                return parts[1] if len(parts) > 1 else "未知"
    except:
        pass
    return "未知"

def export_context(session_id):
    """導出最後幾輪對話作為上下文"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tmp = f.name
        subprocess.run(['opencode', 'export', session_id], stdout=open(tmp, 'w'),
                      stderr=subprocess.DEVNULL, timeout=10)
        with open(tmp) as f:
            data = json.loads(f.read()[f.read().find('{'):])
        Path(tmp).unlink()
        
        # 提取最後 5 條文本
        texts = []
        for msg in data.get('messages', [])[-5:]:
            for part in msg.get('parts', []) if isinstance(msg, dict) else []:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text = part.get('text', '')[:500]
                    if text:
                        texts.append(text)
        
        return '\n'.join(texts[-3:]) if texts else ''
    except:
        return ''

def create_session(old_id, task_name, context):
    """創建新 session（帶上下文）"""
    old_sessions = set(subprocess.run(['opencode', 'session', 'list'],
                       capture_output=True, text=True).stdout.split('\n'))
    
    prompt = f"繼續之前的{task_name}工作。\n\n上一輪最後的工作內容：\n{context}" if context else f"繼續{task_name}工作"
    subprocess.Popen(['opencode', 'run', prompt], 
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    for _ in range(30):
        time.sleep(1)
        new_sessions = set(subprocess.run(['opencode', 'session', 'list'],
                          capture_output=True, text=True).stdout.split('\n'))
        diff = new_sessions - old_sessions
        for line in diff:
            if line.startswith('ses_'):
                return line.split()[0]
    return None

# ==================== 主邏輯 ====================
def run_with_retry(session_id, prompt, timeout, max_retries):
    """執行命令，支持指數退避重試"""
    max_timeout = 3600  # 最大 1 小時
    
    for retry in range(max_retries + 1):
        current_timeout = min(timeout * (2 ** retry), max_timeout)
        
        if retry > 0:
            warn(f"🔄 重試 #{retry}（超時設為 {current_timeout//60} 分鐘）")
        
        process = subprocess.Popen(['opencode', 'run', '--session', session_id, prompt], text=True)
        start = time.time()
        
        while True:
            if process.poll() is not None:
                return process.returncode == 0
            
            elapsed = time.time() - start
            
            # 超時處理
            if elapsed >= current_timeout:
                process.terminate()
                if retry < max_retries:
                    warn(f"⏱️ 超時（{current_timeout//60} 分鐘），加倍等待時間重試...")
                    break
                else:
                    err(f"達到最大重試次數（{max_retries}），跳過此輪")
                    return False
            
            time.sleep(1)
    return False

def main():
    if len(sys.argv) < 2:
        print("用法: python3 opencode-infinity-lite.py <session_id> [config_name]")
        print("範例: python3 opencode-infinity-lite.py ses_xxx medical-kb")
        sys.exit(1)
    
    session_id = sys.argv[1]
    config_name = sys.argv[2] if len(sys.argv) > 2 else 'medical-kb'
    
    # 載入配置
    print(f"使用配置: {config_name}")
    cfg = load_config(config_name)
    
    task_name = cfg.get('task', {}).get('name', '通用任務')
    language = cfg.get('task', {}).get('language', '繁體中文')
    max_tokens = cfg.get('opencode', {}).get('max_tokens', 128000)
    threshold = cfg.get('opencode', {}).get('token_threshold', 0.7)
    delay = cfg.get('execution', {}).get('delay', 1)
    timeout = cfg.get('execution', {}).get('timeout', 300)
    max_retries = cfg.get('execution', {}).get('max_retries', 5)
    prompts = cfg.get('prompts', ['繼續工作'])
    summary_prompt = cfg.get('summary_prompt', '總結本輪工作')
    
    # 顯示啟動信息
    sep()
    log(f"OpenCode Infinity Lite 啟動")
    print(f"任務: {task_name} | Token 閾值: {int(threshold*100)}% | 語言: {language}")
    sep()
    print()
    
    round_num = 0
    session_num = 1
    start_time = datetime.now()
    
    try:
        while True:
            round_num += 1
            
            # 顯示輪次信息
            sep()
            log(f"第 {round_num} 輪 | Session {session_num}-{round_num if session_num == 1 else round_num % session_num or 1} | {datetime.now().strftime('%H:%M:%S')}")
            
            # Token 檢查
            tokens = get_tokens(session_id)
            if tokens:
                pct = tokens / max_tokens * 100
                color = C.G if pct < 50 else C.Y if pct < threshold * 100 else C.E
                print(f"Session ID: {session_id}")
                title = get_title(session_id)
                if title != "未知":
                    print(f"標題: {title}")
                print(f"{color}Token: {tokens:,}/{max_tokens:,} ({pct:.1f}%){C.R}")
                
                # 判斷是否需要切換
                if pct >= threshold * 100:
                    sep()
                    log(f"Session {session_num} 達到 Token 閾值，開始總結...")
                    sep()
                    print()
                    
                    # 執行總結
                    run_with_retry(session_id, summary_prompt, timeout, max_retries)
                    
                    print()
                    sep()
                    ok(f"✓ Session {session_num} 總結完成")
                    sep()
                    print()
                    
                    # 創建新 session
                    log("創建新 Session...")
                    context = export_context(session_id)
                    new_id = create_session(session_id, task_name, context)
                    
                    if new_id:
                        ok(f"已創建新 Session")
                        print(f"{C.Y}舊 Session: {session_id}{C.R}")
                        print(f"{C.G}新 Session: {new_id}{C.R}")
                        session_id = new_id
                        session_num += 1
                        round_num = 0
                        continue
                    else:
                        err("無法創建新 session（30秒超時）")
                        break
            
            sep()
            print()
            
            # 執行提示詞
            log(f"執行提示詞 #{(round_num - 1) % len(prompts) + 1}")
            print()
            
            prompt = prompts[(round_num - 1) % len(prompts)]
            if run_with_retry(session_id, prompt, timeout, max_retries):
                print()
                ok("本輪完成")
                print()
            else:
                print()
                err("本輪失敗，繼續下一輪")
                print()
            
            time.sleep(delay)
            
    except KeyboardInterrupt:
        # 顯示統計
        elapsed = datetime.now() - start_time
        hours = elapsed.seconds // 3600
        minutes = (elapsed.seconds % 3600) // 60
        
        print(f"\n\n{'═'*70}")
        log("已停止")
        print(f"共 {round_num} 輪 | 用時 {hours}小時{minutes}分鐘")
        sep()
        print()

if __name__ == '__main__':
    main()
