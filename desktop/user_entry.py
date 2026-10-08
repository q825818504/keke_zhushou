"""Public client: only a read-only asset server and desktop window."""
import argparse
import json
from pathlib import Path
from inventory.service import InventoryService
from vision.service import VisionService
from native.components import ComponentManager
from runtime import APP_DATA, BUNDLE, guarded, launch_window, public_server, single_instance, local_workspace

SMOKE = """(() => {
 const checks = {};
 checks.noAdmin = !document.querySelector('#userAdminButton, #roleManagementView, #repoSyncButton');
 checks.defaultTeam = userActiveRoute === 'team' && !!document.querySelector('#userTeamRoute').textContent.trim();
 checks.characters = Object.keys(characterData).length >= 25;
 const savedOwned = userTeamOwnedNames;
 userTeamOwnedNames = new Set(Object.keys(characterData));
 const first = userTeamRecommendPlans()[0];
 const second = first && userTeamRecommendPlans("", new Set(first.memberNames))[0];
 checks.pairing = !!first && first.memberNames.length === 4 && !!second && second.memberNames.length === 4 &&
   !first.memberNames.some(name => second.memberNames.includes(name));
 checks.templates = teamTemplateKnowledge.teams.length >= 27;
 userTeamOwnedNames = savedOwned;
 for (const route of ['characters','arc-drives','cassettes','drive-blocks','inventory','vision']) {
   showUserRoute(route);
   const panel = document.querySelector('[data-user-route-panel="' + route + '"]');
   checks[route] = !!panel && !panel.hidden && panel.textContent.trim().length > 20;
 }
 showUserRoute('characters');
 for (const name of Object.keys(characterData).slice(0,3)) applyCharacter(name);
 checks.selection = activeKnowledge.name === selectedCharacter;
 for (const tab of ['skills','build','cultivation']) {
   userActiveTab = tab; renderUserTabPanel(activeKnowledge);
   checks[tab] = document.querySelector('#userTabPanel').textContent.trim().length > 20;
 }
 showUserRoute('inventory');
 checks.visionModule = typeof window.KekeVision?.render === 'function';
 checks.inventoryModule = typeof window.KekeInventory?.render === 'function';
 return { checks, errors: window.__desktopErrors, title: document.title,
   characterCount: Object.keys(characterData).length, viewport: [innerWidth,innerHeight] };
})()"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-report")
    parser.add_argument("--screenshot")
    parser.add_argument('--vision-self-test')
    parser.add_argument('--native-self-test')
    args = parser.parse_args()
    if args.native_self_test:
        import subprocess, tempfile, traceback
        manager=ComponentManager(APP_DATA / 'native-components')
        try:
            bundle=manager.component_root()
            with tempfile.TemporaryDirectory(prefix='keke-core-check-') as directory:
                process=subprocess.run([str(bundle/'nte-core.exe'),'version','--json'],cwd=directory,capture_output=True,text=True,encoding='utf-8',timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if process.returncode:raise RuntimeError(process.stderr or 'Core startup failed')
            version=json.loads(process.stdout)
            result={'ok':version.get('core_version')=='0.4.4','version':version,'verified_files':len(manager.identity['files']),
                    'bundled_core':str(bundle/'nte-core.exe'),'external_calculator_required':False,'empty_working_directory':True}
        except Exception:result={'ok':False,'error':traceback.format_exc()}
        Path(args.native_self_test).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return
    if args.vision_self_test:
        import traceback
        from vision.smoke import check_bundle
        try:result=check_bundle()
        except Exception:result={'ok':False,'error':traceback.format_exc()}
        Path(args.vision_self_test).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return
    if not args.smoke_report and not single_instance("可可助手", "user"):
        return
    root = BUNDLE / "public" if (BUNDLE / "public").exists() else Path(__file__).resolve().parents[1] / "build/desktop/public"
    vision = VisionService(APP_DATA / "vision-scans")
    components = ComponentManager(APP_DATA / "native-components")
    inventory = InventoryService(APP_DATA / "player-inventory", components=components, vision=vision)
    server = public_server(root, 0 if args.smoke_report else 8767, workspace=local_workspace,
                           inventory=inventory, vision=vision)
    launch_window("可可助手", "user", server, report=args.smoke_report, screenshot=args.screenshot, smoke_js=SMOKE)


if __name__ == "__main__":
    guarded(main)
