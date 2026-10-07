"""Public client: only a read-only asset server and desktop window."""
import argparse
from pathlib import Path
from runtime import BUNDLE, guarded, launch_window, public_server, single_instance, local_workspace

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
 for (const route of ['characters','arc-drives','cassettes','drive-blocks']) {
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
 showUserRoute('team');
 return { checks, errors: window.__desktopErrors, title: document.title,
   characterCount: Object.keys(characterData).length, viewport: [innerWidth,innerHeight] };
})()"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-report")
    parser.add_argument("--screenshot")
    args = parser.parse_args()
    if not args.smoke_report and not single_instance("可可助手", "user"):
        return
    root = BUNDLE / "public" if (BUNDLE / "public").exists() else Path(__file__).resolve().parents[1] / "build/desktop/public"
    server = public_server(root, 0 if args.smoke_report else 8767, workspace=local_workspace)
    launch_window("可可助手", "user", server, report=args.smoke_report, screenshot=args.screenshot, smoke_js=SMOKE)


if __name__ == "__main__":
    guarded(main)
