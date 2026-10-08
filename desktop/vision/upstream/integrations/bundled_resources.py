from pathlib import Path

def bundled_root():return Path(__file__).resolve().parents[2]/'resources'
def bundled_config_dir():return bundled_root()/'config'
def bundled_ocr_model_dir():return bundled_root()/'models'
def bundled_game_ui_asset_root():return bundled_root()/'game_ui'
