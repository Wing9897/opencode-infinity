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
                'run_session': ['codex', 'run', '--session', '--skip-git-repo-check'],
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
    config_file = None
    config_name = None
    
    # 方法 1: 檢查是否為文件路徑（包含 / 或 .yaml）
    if '/' in config_input or config_input.endswith('.yaml') or config_input.endswith('.yml'):
        # 處理文件路徑
        if config_input.startswith('/'):
            # 絕對路徑
            config_file = Path(config_input)
        elif config_input.startswith('tasks_yaml/'):
            # 相對路徑（已包含目錄）
            config_file = Path(config_input)
        else:
            # 只有文件名，添加 tasks_yaml/ 前綴
            config_file = Path(f'tasks_yaml/{config_input}')
        
        if not config_file.exists():
            err(f"配置文件不存在: {config_file}")
            sys.exit(1)
        
        # 從文件名提取配置名稱（去掉 .yaml 後綴）
        config_name = config_file.stem
        
    else:
        # 方法 2: 配置名稱（不包含路徑和後綴）
        config_name = config_input
        
        # 驗證配置名稱
        if not re.match(r'^[a-zA-Z0-9_-]+$', config_name):
            err(f"無效的配置名稱: {config_name}")
            sys.exit(1)
        
        # 嘗試直接配置文件
        config_file = Path(f'tasks_yaml/{config_name}.yaml')
        if not config_file.exists():
            # 嘗試嵌套配置
            if '-' in config_name:
                parts = config_name.split('-')
                for i in range(len(parts) - 1, 0, -1):
                    base_name = '-'.join(parts[:i])
                    base_file = Path(f'tasks_yaml/{base_name}.yaml')
                    
                    if base_file.exists():
                        config_file = base_file
                        break
            
            if not config_file or not config_file.exists():
                warn(f"配置不存在: {config_name}，使用默認配置")
                return {
                    'task': {'name': '通用任務', 'language': '繁體中文'},
                    'cli': {'tool': 'opencode', 'commands': {}},
                    'opencode': {'max_tokens': 128000, 'token_threshold': 0.7},
                    'execution': {'delay': 1, 'timeout': 300, 'max_retries': 5},
                    'prompts': ['繼續工作']
                }
    
    # 載入 YAML 文件
    with open(config_file) as f:
        data = yaml.safe_load(f)
    
    # 提取配置
    cfg = None
    
    # 檢查是否為嵌套配置
    if config_name in data:
        cfg = data[config_name]
        ok(f"已加載配置: {config_file.name} -> {config_name}")
    elif len(data) == 1 and isinstance(list(data.values())[0], dict):
        # 單個嵌套配置
        key = list(data.keys())[0]
        cfg = data[key]
        ok(f"已加載配置: {config_file.name} -> {key}")
    else:
        # 直接配置
        cfg = data
        ok(f"已加載配置: {config_file.name}")
    
    # 顯示配置信息
    cli_tool = cfg.get('cli', {}).get('tool', 'opencode')
    print(f"  CLI 工具: {cli_tool}")
    if 'task' in cfg and 'output_dir' in cfg['task']:
        print(f"  輸出目錄: {cfg['task']['output_dir']}/\n")
    
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

# ==================== 命令執行 ====================

def run_with_retry(session_id, prompt, timeout, max_retries, cli):
    """執行 CLI 命令，支持重試機制"""
    max_timeout = 3600  # 最大 1 小時
    
    for retry in range(max_retries + 1):
        current_timeout = min(timeout * (2 ** retry), max_timeout)
        
        if retry > 0:
            warn(f"🔄 重試 #{retry}（超時設為 {current_timeout//60} 分鐘）")
        
        process = subprocess.Popen(cli.run_session(session_id, prompt), text=True)
        start = time.time()
        
        while True:
            if process.poll() is not None:
                return process.returncode == 0
            
            elapsed = time.time() - start
            
            if elapsed >= current_timeout:
                process.terminate()
                if retry < max_retries:
                    warn(f"⏱️ 超時（{current_timeout//60} 分鐘），重試...")
                    break
                else:
                    err(f"達到最大重試次數（{max_retries}），跳過")
                    return False
            
            time.sleep(1)
    return False

# ==================== 主程序 ====================

def main():
    """主程序入口"""
    if len(sys.argv) < 2:
        print("用法: python3 opencode-infinity.py <session_id> [config]")
        print("\n配置格式支持：")
        print("  1. 配置名稱：medical-kb-codex")
        print("  2. 文件名：medical-kb.yaml")
        print("  3. 相對路徑：tasks_yaml/medical-kb.yaml")
        print("  4. 絕對路徑：/home/user/config.yaml")
        print("\n範例：")
        print("  python3 opencode-infinity.py ses_api api-development-codex")
        print("  python3 opencode-infinity.py ses_api medical-kb.yaml")
        print("  python3 opencode-infinity.py ses_api tasks_yaml/testing.yaml")
        sys.exit(1)
    
    # 驗證 session_id
    session_id = sys.argv[1]
    if not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        err(f"無效的 session ID: {session_id}")
        sys.exit(1)
    
    config_name = sys.argv[2] if len(sys.argv) > 2 else 'medical-kb'
    
    # 載入配置
    print(f"使用配置: {config_name}")
    cfg = load_config(config_name)
    
    # 初始化 CLI 適配器
    cli_config = cfg.get('cli', {})
    cli_tool = cli_config.get('tool', 'opencode')
    cli_commands = cli_config.get('commands', {})
    cli = CLIAdapter(cli_tool, cli_commands)
    
    # 讀取配置參數
    task_name = cfg.get('task', {}).get('name', '通用任務')
    language = cfg.get('task', {}).get('language', '繁體中文')
    max_tokens = cfg.get('opencode', {}).get('max_tokens', 128000)
    threshold = cfg.get('opencode', {}).get('token_threshold', 0.7)
    delay = cfg.get('execution', {}).get('delay', 1)
    timeout = cfg.get('execution', {}).get('timeout', 300)
    max_retries = cfg.get('execution', {}).get('max_retries', 5)
    
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
    
    # 切換策略
    switch_strategy = cfg.get('execution', {}).get('switch_strategy', 'auto')
    if switch_strategy == 'auto':
        switch_strategy = 'token' if cli.supports_export() else 'rounds'
    
    # 顯示啟動信息
    sep()
    log(f"OpenCode Infinity 啟動")
    print(f"CLI 工具: {cli_tool.upper()} | 任務: {task_name}")
    print(f"切換策略: {switch_strategy.upper()} | 語言: {language}")
    sep()
    print()
    
    round_num = 0
    start_time = datetime.now()
    session_count = 1  # Session 計數器
    
    try:
        while True:
            round_num += 1
            
            # 顯示輪次信息
            sep()
            log(f"第 {round_num} 輪 | Session #{session_count} | {datetime.now().strftime('%H:%M:%S')}")
            
            # Token 統計（僅 OpenCode）
            should_switch = False
            if switch_strategy == 'token':
                tokens = get_tokens(session_id, cli)
                if tokens:
                    pct = tokens / max_tokens * 100
                    color = C.G if pct < 50 else C.Y if pct < threshold * 100 else C.E
                    print(f"Session ID: {session_id}")
                    print(f"{color}Token: {tokens:,}/{max_tokens:,} ({pct:.1f}%){C.R}")
                    
                    if pct >= threshold * 100:
                        should_switch = True
                        warn(f"達到 Token 閾值 ({pct:.1f}%)，準備切換 Session")
            else:
                print(f"Session ID: {session_id}")
            
            sep()
            print()
            
            # 如果需要切換 Session，先執行總結
            if should_switch:
                log("執行總結提示詞")
                print()
                
                if run_with_retry(session_id, summary_prompt, timeout, max_retries, cli):
                    print()
                    ok("總結完成")
                    print()
                else:
                    print()
                    warn("總結失敗，繼續切換")
                    print()
                
                # 生成新的 Session ID
                old_session = session_id
                session_count += 1
                session_id = f"{session_id.rsplit('_', 1)[0]}_{session_count}" if '_' in session_id else f"{session_id}_{session_count}"
                
                sep()
                log(f"切換 Session: {old_session} → {session_id}")
                sep()
                print()
                
                time.sleep(delay)
                continue
            
            # 執行提示詞
            log(f"執行提示詞 #{(round_num - 1) % len(prompts) + 1}")
            print()
            
            prompt = prompts[(round_num - 1) % len(prompts)]
            if run_with_retry(session_id, prompt, timeout, max_retries, cli):
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
        print(f"共 {round_num} 輪 | {session_count} 個 Session | 用時 {hours}小時{minutes}分鐘")
        sep()
        print()

if __name__ == '__main__':
    main()
