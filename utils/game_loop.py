"""Re-arming phase timers for games restored after a restart."""

import time

from utils.game_logic import resolve_afsungar, resolve_night, resolve_vote, start_voting
from utils.lobby import finish_lobby
from utils.night_actions import veyron_notice_job, zombie_convert_job
from utils.state import cancel_jobs, games


def resume_games(app):
    now=time.time()
    for g in list(games.values()):
        phase=g.get("phase")
        if phase in {"ended","cancelled","starting"}: continue
        remaining=max(0,int(g.get("phase_ends_at",now)-now))
        if phase=="lobby": fn=finish_lobby; name="lobby-resume"
        elif phase=="night": fn=resolve_night; name="night-resume"
        elif phase=="discussion": fn=start_voting; name="discussion-resume"
        elif phase=="afsungar": fn=resolve_afsungar; name="afsungar-resume"
        elif phase=="voting": fn=resolve_vote; name="vote-resume"
        else: continue
        cancel_jobs(g)
        g["jobs"]=[app.job_queue.run_once(fn,remaining,data={"gid":g["id"],"phase":g["phase_id"]},name=f"{name}-{g['id']}")]
        if phase=="night" and g.get("mode")=="zombie" and g.get("mode_state",{}).get("zombie_pending"):
            rem_to_dawn=max(0,int(g.get("phase_ends_at",now)-now)-5)
            app.job_queue.run_once(zombie_convert_job,max(0,rem_to_dawn),data={"gid":g["id"]},name=f"zombie-resume-{g['id']}")
        if phase=="night" and g.get("veyron_notice"):
            rem_to_notice=max(0,int(g.get("phase_ends_at",now)-now)-5)
            app.job_queue.run_once(veyron_notice_job,max(0,rem_to_notice),data={"gid":g["id"]},name=f"veyron-resume-{g['id']}")
