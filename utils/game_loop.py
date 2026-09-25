"""Re-arming phase timers for games restored after a restart."""

import time

from telegram.error import TelegramError

from utils.game_logic import resolve_afsungar, resolve_confirm, resolve_night, resolve_revenge, resolve_vote, start_day, start_voting
from utils.lobby import finish_lobby
from utils.night_actions import veyron_notice_job, zombie_convert_job
from utils.state import cancel_game, cancel_jobs, find_game, games


async def resume_day_job(ctx):
    """Night was already resolved when the bot stopped; continue straight to dawn."""
    g=find_game(ctx.job.data.get("gid"))
    if not g or g.get("phase")!="day": return
    await start_day(ctx.application,g)


async def notify_cancelled_job(ctx):
    try: await ctx.bot.send_message(ctx.job.data["chat_id"],"⚠️ Bot o‘yin boshlanayotgan paytda qayta ishga tushdi, shuning uchun o‘yin bekor qilindi. Yangi o‘yin uchun /game yuboring.")
    except TelegramError: pass


def resume_games(app):
    now=time.time()
    for g in list(games.values()):
        phase=g.get("phase")
        if phase in {"ended","cancelled"}: continue
        if phase=="starting":
            # Roles were only partly handed out; the game cannot be resumed safely.
            cancel_game(g)
            app.job_queue.run_once(notify_cancelled_job,1,data={"chat_id":g["chat_id"]},name=f"starting-cancel-{g['id']}")
            continue
        remaining=max(0,int(g.get("phase_ends_at",now)-now))
        if phase=="lobby": fn=finish_lobby; name="lobby-resume"
        elif phase=="night": fn=resolve_night; name="night-resume"
        elif phase=="day": fn=resume_day_job; name="day-resume"; remaining=1
        elif phase=="discussion": fn=start_voting; name="discussion-resume"
        elif phase=="afsungar": fn=resolve_afsungar; name="afsungar-resume"
        elif phase=="voting": fn=resolve_vote; name="vote-resume"
        elif phase=="confirm": fn=resolve_confirm; name="confirm-resume"
        elif phase=="revenge": fn=resolve_revenge; name="revenge-resume"
        else: continue
        cancel_jobs(g)
        g["jobs"]=[app.job_queue.run_once(fn,remaining,data={"gid":g["id"],"phase":g["phase_id"]},name=f"{name}-{g['id']}")]
        if phase=="night" and g.get("mode")=="zombie" and g.get("mode_state",{}).get("zombie_pending"):
            rem_to_dawn=max(0,int(g.get("phase_ends_at",now)-now)-5)
            app.job_queue.run_once(zombie_convert_job,max(0,rem_to_dawn),data={"gid":g["id"]},name=f"zombie-resume-{g['id']}")
        if phase=="night" and g.get("veyron_notice"):
            rem_to_notice=max(0,int(g.get("phase_ends_at",now)-now)-5)
            app.job_queue.run_once(veyron_notice_job,max(0,rem_to_notice),data={"gid":g["id"]},name=f"veyron-resume-{g['id']}")
