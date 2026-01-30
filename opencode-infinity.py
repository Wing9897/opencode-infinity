#!/usr/bin/env python3
"""
OpenCode Infinity - 簡化版

多 CLI 工具自動執行系統，支持 OpenCode、Claude、Codex、Copilot。

使用方法:
    python3 opencode-infinity.py <session_id> <config_name>
"""
import subprocess
import sys
import time
import json
import tempfile
import re
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("錯誤：pip3 install pyyaml")

# ==================== 顏色輸出 ====================

class C:
    """ANSI 顏色代碼"""
    R = '\033[0m'   # 重置
    B = '\033[94m'  # 藍
    G = '\033[92m'  # 綠
    Y = '\033[93m'  # 黃
    E = '\033[91m'  # 紅

def log(msg): print(f"{C.B}[腳本] {msg}{C.R}")
def ok(msg): print(f"{C.G}✓ {msg}{C.R}")
def warn(msg): print(f"{C.Y}⚠ {msg}{C.R}")
def err(msg): print(f"{C.E}✗ {msg}{C.R}")
def sep(): print("═" * 70)

# ==================== CLI 適配器 ====================

class CLIAdapter:
    """CLI 工具適配器，支持 opencode, claude, codex, copilot"""
    
    def __init__(self, tool='opencode', custom_commands=None):
        self.tool = tool.lower()
        self.commands = self._get_default_commands()
        
        # 覆蓋自定義命令
        if custom_commands:
            for cmd_name, cmd_value in custom_commands.items():
                if cmd_value and cmd_value.strip():
                    self.commands[cmd_name] = cmd_value.split()
    
    def _get_default_commands(self):
        """獲取默認命令配置"""
        defaults = {
            'opencode': {
                'run': ['opencode', 'run'],
                'run_session': ['opencode', 'run', '--session'],
                'export': ['opencode', 'export'],
            },
            'claude': {
                'run': ['claude'],
                'run_session': ['claude', '--resume'],
                'export': ['claude', 'export'],
            },
            'codex': {
                'run': ['codex', 'run', '--skip-git-repo-check'],
                'run_session': ['codex', 'exec', 'resume', '--last', '--skip-git-repo-check'],
            },
            'copilot': {
                'run': ['gh', 'copilot', 'explain'],
            }
        }
        return defaults.get(self.tool, defaults['opencode']).copy()
    
    def get_cmd(self, cmd_type):
        """獲取命令，如果不存在則拋出異常"""
        cmd = self.commands.get(cmd_type)
        if cmd is None:
            raise ValueError(f"{self.tool} 不支持 {cmd_type} 命令")
        return cmd
    
    def run_session(self, session_id, prompt):
        """
        執行帶會話的 CLI 命令
        
        特殊處理：
        - Codex 的 "exec resume --last" 格式不插入 session_id
        - 其他工具使用標準格式：command + session_id + prompt
        """
        cmd = self.get_cmd('run_session')
        
        # 處理空 prompt
        if not prompt or not prompt.strip():
            warn("Prompt 為空，使用默認值")
            prompt = "繼續工作"
        
        # Codex 特殊處理：exec resume --last 格式
        cmd_str = ' '.join(cmd)
        if self.tool == 'codex' and 'exec' in cmd_str and 'resume' in cmd_str:
            return cmd + [prompt]
        
        # 標準格式
        return cmd + [session_id, prompt]
    
    def export(self, session_id):
        """導出 session 數據"""
        return self.get_cmd('export') + [session_id]
    
    def supports_export(self):
        """是否支持 export 命令"""
        return 'export' in self.commands

# ==================== 配置載入 ====================

def load_config(config_input):
    """
    從 YAML 文件載入配置
    
    支持多種格式：
    1. 配置名稱：medical-kb-codex
    2. 文件名：medical-kb.yaml
    3. 相對路徑：tasks_yaml/medical-kb.yaml
    4. 絕對路徑：/home/user/config.yaml
    """
    # 確定配置文件路徑
    if '/' in config_input or config_input.endswith(('.yaml', '.yml')):
        # 文件路徑模式
        if config_input.startswith('/'):
            config_file = Path(config_input)
        elif config_input.startswith('tasks_yaml/'):
            config_file = Path(config_input)
        else:
            config_file = Path(f'tasks_yaml/{config_input}')
        config_name = config_file.stem
    else:
        # 配置名稱模式
        config_name = config_input
        if not re.match(r'^[a-zA-Z0-9_-]+$', config_name):
            err(f"無效的配置名稱: {config_name}")
            sys.exit(1)
        
        # 查找配置文件
        config_file = Path(f'tasks_yaml/{config_name}.yaml')
        if not config_file.exists() and '-' in config_name:
            # 嘗試嵌套配置
            for i in range(len(config_name.split('-')) - 1, 0, -1):
                base_file = Path(f"tasks_yaml/{'-'.join(config_name.split('-')[:i])}.yaml")
                if base_file.exists():
                    config_file = base_file
                    break
    
    # 檢查文件是否存在
    if not config_file.exists():
        warn(f"配置不存在: {config_input}，使用默認配置")
        return {
            'task': {'name': '通用任務', 'language': '繁體中文'},
            'cli': {'tool': 'opencode', 'commands': {}},
            'opencode': {'max_tokens': 128000, 'token_threshold': 0.7},
            'execution': {'delay': 1, 'timeout': 300, 'max_retries': 5},
            'prompts': ['繼續工作']
        }
    
    # 載入並解析 YAML
    with open(config_file) as f:
        data = yaml.safe_load(f)
    
    # 提取配置（支持嵌套和直接配置）
    if config_name in data:
        cfg = data[config_name]
        ok(f"已加載配置: {config_file.name} -> {config_name}")
    elif len(data) == 1 and isinstance(list(data.values())[0], dict):
        key = list(data.keys())[0]
        cfg = data[key]
        ok(f"已加載配置: {config_file.name} -> {key}")
    else:
        cfg = data
        ok(f"已加載配置: {config_file.name}")
    
    # 不再顯示配置信息（已合併到啟動信息中）
    
    return cfg

# ==================== Token 統計 ====================

def get_tokens(session_id, cli):
    """獲取 session 的 token 使用量（僅 OpenCode 支持）"""
    if not cli.supports_export():
        return None
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tmp = f.name
        subprocess.run(cli.export(session_id), stdout=open(tmp, 'w'), 
                      stderr=subprocess.DEVNULL, timeout=10)
        with open(tmp) as f:
            content = f.read()
            data = json.loads(content[content.find('{'):])
        Path(tmp).unlink()
        
        # 累加所有 output tokens
        total_output = 0
        for msg in data.get('messages', []):
            for part in msg.get('parts', []) if isinstance(msg, dict) else []:
                if isinstance(part, dict) and part.get('type') == 'step-finish':
                    total_output += part.get('tokens', {}).get('output', 0)
        return total_output
    except:
        return None

def get_title(session_id, cli):
    """獲取 session 標題（僅 OpenCode 支持）"""
    if cli.tool != 'opencode':
        return None
    
    try:
        result = subprocess.run(['opencode', 'session', 'list'], 
                              capture_output=True, text=True, timeout=5)
        for line in result.stdout.split('\n'):
            if line.startswith(session_id):
                parts = line.split(maxsplit=2)
                return parts[1] if len(parts) > 1 else None
    except:
        pass
    return None

def export_context(session_id, cli):
    """導出最後幾輪對話作為上下文（僅 OpenCode 支持）"""
    if not cli.supports_export():
        return ''
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tmp = f.name
        subprocess.run(cli.export(session_id), stdout=open(tmp, 'w'),
                      stderr=subprocess.DEVNULL, timeout=10)
        with open(tmp) as f:
            content = f.read()
            data = json.loads(content[content.find('{'):])
        Path(tmp).unlink()
        
        # 提取最後 5 條文本消息
        texts = []
        for msg in data.get('messages', [])[-5:]:
            for part in msg.get('parts', []) if isinstance(msg, dict) else []:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text = part.get('text', '')[:500]  # 限制每條 500 字符
                    if text:
                        texts.append(text)
        
        # 返回最後 3 條
        return '\n'.join(texts[-3:]) if texts else ''
    except:
        return ''

def create_session(old_id, task_name, context, cli):
    """創建新 session（帶上下文，僅 OpenCode 支持）"""
    if cli.tool != 'opencode':
        return None
    
    try:
        # 獲取當前所有 session
        old_sessions = set(subprocess.run(['opencode', 'session', 'list'],
                                        capture_output=True, text=True).stdout.split('\n'))
        
        # 構建帶上下文的提示詞
        if context:
            prompt = f"繼續之前的{task_name}工作。\n\n上一輪最後的工作內容：\n{context}"
        else:
            prompt = f"繼續{task_name}工作"
        
        # 創建新 session
        subprocess.Popen(['opencode', 'run', prompt], 
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 等待新 session 出現（最多 30 秒）
        for _ in range(30):
            time.sleep(1)
            new_sessions = set(subprocess.run(['opencode', 'session', 'list'],
                                            capture_output=True, text=True).stdout.split('\n'))
            diff = new_sessions - old_sessions
            for line in diff:
                if line.startswith('ses_'):
                    return line.split()[0]
        
        return None
    except:
        return None

# ==================== 配置解析 ====================

def parse_config(cfg):
    """解析配置並返回所有參數"""
    def get_config(section, key, default=None):
        """輔助函數：安全獲取配置值"""
        return cfg.get(section, {}).get(key, default)
    
    # 任務配置
    task_name = get_config('task', 'name', '通用任務')
    task_desc = get_config('task', 'description', '')
    language = get_config('task', 'language', '繁體中文')
    output_dir = get_config('task', 'output_dir', 'output')
    
    # OpenCode 設置
    model = get_config('opencode', 'model', 'default')
    max_tokens = get_config('opencode', 'max_tokens', 128000)
    threshold = get_config('opencode', 'token_threshold', 0.7)
    
    # 執行設置
    delay = get_config('execution', 'delay', 1)
    timeout = get_config('execution', 'timeout', 300)
    max_retries = get_config('execution', 'max_retries', 5)
    auto_continue = get_config('execution', 'auto_continue_on_error', True)
    max_rounds = get_config('execution', 'max_rounds', 0)  # 0 = 無限制
    
    # 顯示設置
    display_cfg = cfg.get('display', {})
    show_session_id = display_cfg.get('show_session_id', True)
    show_token_usage = display_cfg.get('show_token_usage', True)
    show_timestamp = display_cfg.get('show_timestamp', True)
    
    # 處理 prompts
    raw_prompts = cfg.get('prompts', ['繼續工作'])
    prompts = []
    for p in raw_prompts:
        if isinstance(p, dict):
            prompts.append(p.get('content', '繼續工作'))
        elif isinstance(p, str):
            prompts.append(p)
        else:
            prompts.append('繼續工作')
    
    # 總結提示詞
    summary_prompt = cfg.get('summary_prompt', '總結本輪工作（300字內）')
    
    return {
        'task_name': task_name, 'task_desc': task_desc, 
        'language': language, 'output_dir': output_dir,
        'model': model, 'max_tokens': max_tokens, 'threshold': threshold,
        'delay': delay, 'timeout': timeout, 
        'max_retries': max_retries, 'auto_continue': auto_continue,
        'max_rounds': max_rounds,
        'show_session_id': show_session_id, 
        'show_token_usage': show_token_usage, 
        'show_timestamp': show_timestamp,
        'prompts': prompts, 'summary_prompt': summary_prompt
    }

# ==================== 命令執行 ====================

def run_with_retry(session_id, prompt, timeout, max_retries, cli):
    """執行 CLI 命令，支持重試機制"""
    max_timeout = 3600  # 最大 1 小時
    retry_delay = 3     # 重試間隔（秒）
    
    for retry in range(max_retries + 1):
        current_timeout = min(timeout * (2 ** retry), max_timeout)
        
        if retry > 0:
            warn(f"🔄 重試 #{retry}（超時設為 {current_timeout//60} 分鐘）")
            # 重試前等待一段時間
            print(f"   等待 {retry_delay} 秒後重試...")
            time.sleep(retry_delay)
        
        process = subprocess.Popen(cli.run_session(session_id, prompt), text=True)
        start = time.time()
        
        while True:
            if process.poll() is not None:
                # 進程已結束
                if process.returncode == 0:
                    return True
                else:
                    # 進程錯誤退出
                    if retry < max_retries:
                        warn(f"進程異常退出（返回碼: {process.returncode}），準備重試...")
                        break
                    else:
                        err(f"達到最大重試次數（{max_retries}），跳過")
                        return False
            
            elapsed = time.time() - start
            
            if elapsed >= current_timeout:
                # 超時，終止進程
                process.terminate()
                try:
                    process.wait(timeout=5)  # 等待進程優雅退出
                except subprocess.TimeoutExpired:
                    process.kill()  # 強制終止
                
                if retry < max_retries:
                    warn(f"⏱️ 超時（{current_timeout//60} 分鐘），重試...")
                    break
                else:
                    err(f"達到最大重試次數（{max_retries}），跳過")
                    return False
            
            time.sleep(1)
    return False

# ==================== 主程序輔助函數 ====================

def display_startup_info(config_name, cli_tool, params, switch_strategy):
    """顯示啟動信息"""
    print(f"使用配置: {config_name}")
    print(f"{C.Y}💡 提示：運行中可隨時修改 YAML 配置，每輪自動熱更新{C.R}\n")
    
    sep()
    log(f"OpenCode Infinity 啟動")
    print(f"  CLI 工具: {cli_tool.upper()}")
    print(f"  任務: {params['task_name']}")
    if params['task_desc']:
        print(f"  描述: {params['task_desc']}")
    if params['model'] != 'default':
        print(f"  模型: {params['model']}")
    print(f"  切換策略: {switch_strategy.upper()}")
    if params['max_rounds'] > 0:
        print(f"  最大輪次: {params['max_rounds']} 輪")
    print(f"  語言: {params['language']}")
    print(f"  輸出目錄: {params['output_dir']}/")
    sep()
    print()

def display_round_info(round_num, session_count, session_id, params, 
                       switch_strategy, cli, should_switch_callback):
    """顯示輪次信息並返回是否需要切換 Session"""
    sep()
    timestamp = datetime.now().strftime('%H:%M:%S') if params['show_timestamp'] else ''
    log(f"第 {round_num} 輪 | Session #{session_count}" + 
        (f" | {timestamp}" if timestamp else ""))
    
    should_switch = False
    if switch_strategy == 'token':
        tokens = get_tokens(session_id, cli)
        if tokens and params['show_token_usage']:
            pct = tokens / params['max_tokens'] * 100
            color = C.G if pct < 50 else C.Y if pct < params['threshold'] * 100 else C.E
            if params['show_session_id']:
                print(f"  Session ID: {session_id}")
            
            # 顯示 Session 標題（如果有）
            title = get_title(session_id, cli)
            if title:
                print(f"  標題: {title}")
            
            print(f"  {color}Token: {tokens:,}/{params['max_tokens']:,} ({pct:.1f}%){C.R}")
            
            if pct >= params['threshold'] * 100:
                should_switch = True
                warn(f"達到 Token 閾值 ({pct:.1f}%)，準備切換 Session")
    else:
        if params['show_session_id']:
            print(f"  Session ID: {session_id}")
    
    print()
    return should_switch

def execute_summary_and_switch(session_id, session_count, params, cli):
    """執行總結並生成新的 Session ID（帶上下文傳遞）"""
    log("執行總結提示詞")
    print()
    
    if run_with_retry(session_id, params['summary_prompt'], 
                     params['timeout'], params['max_retries'], cli):
        print()
        ok("總結完成")
        print()
    else:
        print()
        warn("總結失敗，繼續切換")
        print()
    
    # 導出上下文
    log("導出上下文...")
    context = export_context(session_id, cli)
    if context:
        ok(f"已導出上下文（{len(context)} 字符）")
    else:
        warn("無法導出上下文，將創建空白 Session")
    print()
    
    # 嘗試使用上下文創建新 Session（僅 OpenCode 支持）
    task_name = params.get('task_name', '通用任務')
    new_session = create_session(session_id, task_name, context, cli)
    
    if new_session:
        # 成功創建新 Session
        session_count += 1
        sep()
        log(f"切換 Session: {session_id} → {new_session}")
        ok("✓ 已創建新 Session（帶上下文）")
        sep()
        print()
        return new_session, session_count
    else:
        # 回退到舊方法：手動生成 Session ID
        warn("無法自動創建 Session，使用手動生成 ID")
        old_session = session_id
        session_count += 1
        new_session = (f"{session_id.rsplit('_', 1)[0]}_{session_count}" 
                       if '_' in session_id else f"{session_id}_{session_count}")
        
        sep()
        log(f"切換 Session: {old_session} → {new_session}")
        warn("⚠ 新 Session 無上下文，請手動創建")
        sep()
        print()
        
        return new_session, session_count

# ==================== 主程序 ====================

def main():
    """主程序入口"""
    if len(sys.argv) < 2:
        print("用法: python3 opencode-infinity.py <session_id> [config]")
        print("\n配置格式支持：")
        print("  1. 配置名稱：opencode-example")
        print("  2. 文件名：opencode-example.yaml")
        print("  3. 相對路徑：tasks_yaml/opencode-example.yaml")
        print("  4. 絕對路徑：/home/user/config.yaml")
        print("\n範例：")
        print("  python3 opencode-infinity.py ses_open opencode-example")
        print("  python3 opencode-infinity.py ses_codex codex-example")
        print("  python3 opencode-infinity.py ses_test tasks_yaml/opencode-example.yaml")
        sys.exit(1)
    
    # 驗證 session_id
    session_id = sys.argv[1]
    if not re.match(r'^ses[a-zA-Z0-9_-]*$', session_id):
        err(f"無效的 Session ID: {session_id}")
        print(f"{C.Y}提示：Session ID 必須以 'ses' 開頭，例如：ses_test, ses_api{C.R}")
        sys.exit(1)
    
    config_name = sys.argv[2] if len(sys.argv) > 2 else 'opencode-example'
    
    # 載入配置並初始化
    cfg = load_config(config_name)
    cli_config = cfg.get('cli', {})
    cli_tool = cli_config.get('tool', 'opencode')
    cli_commands = cli_config.get('commands', {})
    cli = CLIAdapter(cli_tool, cli_commands)
    params = parse_config(cfg)
    
    # 確定切換策略
    switch_strategy = cfg.get('execution', {}).get('switch_strategy', 'auto')
    if switch_strategy == 'auto':
        switch_strategy = 'token' if cli.supports_export() else 'rounds'
    
    # 顯示啟動信息
    display_startup_info(config_name, cli_tool, params, switch_strategy)
    
    # 主循環
    round_num = 0
    start_time = datetime.now()
    session_count = 1
    
    try:
        while True:
            round_num += 1
            
            # 檢查輪次限制
            if params['max_rounds'] > 0 and round_num > params['max_rounds']:
                print()
                sep()
                log(f"達到最大輪次限制（{params['max_rounds']} 輪），自動停止")
                sep()
                break
            
            # 熱更新配置
            if round_num > 1:
                try:
                    cfg = load_config(config_name)
                    params = parse_config(cfg)
                    log(f"🔄 配置已熱更新")
                except Exception as e:
                    warn(f"配置熱更新失敗，使用舊配置: {e}")
            
            # 顯示輪次信息
            should_switch = display_round_info(
                round_num, session_count, session_id, params, 
                switch_strategy, cli, None
            )
            
            # 處理 Session 切換
            if should_switch:
                session_id, session_count = execute_summary_and_switch(
                    session_id, session_count, params, cli
                )
                time.sleep(params['delay'])
                continue
            
            # 執行提示詞
            log(f"執行提示詞 #{(round_num - 1) % len(params['prompts']) + 1}")
            print()
            
            prompt = params['prompts'][(round_num - 1) % len(params['prompts'])]
            if run_with_retry(session_id, prompt, params['timeout'], 
                            params['max_retries'], cli):
                print()
                ok("本輪完成")
                print()
            else:
                print()
                err("本輪失敗，繼續下一輪")
                print()
            
            time.sleep(params['delay'])
            
    except KeyboardInterrupt:
        # 顯示統計
        elapsed = datetime.now() - start_time
        hours = elapsed.seconds // 3600
        minutes = (elapsed.seconds % 3600) // 60
        
        print(f"\n\n{'═'*70}")
        log("已停止")
        print(f"共 {round_num} 輪 | {session_count} 個 Session | "
              f"用時 {hours}小時{minutes}分鐘")
        sep()
        print()

if __name__ == '__main__':
    main()
