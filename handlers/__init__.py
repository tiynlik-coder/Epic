"""Handler registration. Order matters: block guards (group -100) run before everything else."""

from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters

from .other_handlers import (
    cb_active_role,
    cb_buy,
    cb_menu,
    cb_role,
    cmd_market,
    cmd_profile,
    cmd_start,
)
from .game import (
    cb_action,
    cb_af,
    cb_afs,
    cb_hang,
    cmd_leave,
    cmd_tep,
    cb_amode,
    cb_card,
    cb_kon,
    cb_folbin_msg,
    cb_heroact,
    cb_join,
    cb_katani,
    cb_katani_mode,
    cb_manip2,
    cb_mode,
    cb_prof,
    cb_prof_target,
    cb_res,
    cb_vey1,
    cb_vey2,
    cb_vote,
    cb_zombie,
    cmd_bounty,
    cmd_game,
    cmd_modes,
    cmd_pgame,
    cmd_ngame,
    cmd_stop,
    cmd_ugame,
    cmd_vsgame,
    cmd_zgame,
)
from .admin import (
    admin_callback,
    admin_text_handler,
    cmd_active_games,
    cmd_admin,
    cmd_aktiv,
    cmd_block,
    cmd_blocks,
    cmd_broadcast,
    cmd_bust,
    cmd_bust1,
    cmd_bust2,
    cmd_checkgaming,
    cmd_checkuser,
    cmd_coin,
    cmd_fullbust,
    cmd_gbust,
    cmd_gblock,
    cmd_groups,
    cmd_gsearch,
    cmd_gunblock,
    cmd_heroes,
    cmd_id,
    cmd_inventory,
    cmd_olmos,
    cmd_pul,
    cmd_rgeroy,
    cmd_rgm,
    cmd_scoin,
    cmd_sdiamond,
    cmd_sgeroy,
    cmd_smoney,
    cmd_stopgames,
    cmd_unaktiv,
    cmd_unblock,
    cmd_unvip,
    cmd_vip,
    cmd_you,
    cmd_zapravka1,
    cmd_zapravka7,
)
from .geroy_handlers import (
    hero_callback,
    hero_private_text,
)
from .game_chat import (
    group_write_guard,
    private_game_text,
)
from .pairs import (
    cb_para,
    cmd_dpara,
    cmd_mypara,
    cmd_para,
)
from .economy import (
    GIVEAWAY_ITEMS,
    cb_eco,
    cb_giveaway,
    cb_lottery,
    cmd_change,
    cmd_giveaway,
    cmd_give,
    cmd_ginfo,
    cmd_gsend,
    cmd_money,
    cmd_sgive,
    cmd_tgeroy,
    precheckout,
    successful_payment,
    swap_id_text,
)
from .stats import (
    cmd_boylar,
    cmd_eboylar,
    cmd_gtop,
    cmd_market_stats,
    cmd_tchat,
)
from .stats import cmd_top as cmd_rating_top
from .settings import (
    cb_settings,
    cmd_settings,
)
from .errors import (
    error_handler,
)
from middlewares.block_guard import (
    admin_guard_callback,
    admin_guard_message,
)


async def ignore_button(update, ctx):
    await update.callback_query.answer()


def register_handlers(app):
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("game",cmd_game))
    app.add_handler(CommandHandler("ngame",cmd_ngame))
    app.add_handler(CommandHandler("ugame",cmd_ugame))
    app.add_handler(CommandHandler("zgame",cmd_zgame))
    app.add_handler(CommandHandler("vsgame",cmd_vsgame))
    for _n in range(2,10):
        app.add_handler(CommandHandler(f"vsgame{_n}", lambda update, ctx, n=_n: cmd_vsgame(update,ctx,n)))
    app.add_handler(CommandHandler("bounty",cmd_bounty))
    app.add_handler(CommandHandler("modes",cmd_modes))
    app.add_handler(CommandHandler("stop",cmd_stop))
    app.add_handler(CommandHandler("leave",cmd_leave))
    app.add_handler(CommandHandler(["settings","sozlamalar"],cmd_settings))
    app.add_handler(CommandHandler("pgame",cmd_pgame))
    app.add_handler(CommandHandler("para",cmd_para))
    app.add_handler(CommandHandler("mypara",cmd_mypara))
    app.add_handler(CommandHandler("dpara",cmd_dpara))
    app.add_handler(CommandHandler("money",cmd_money))
    app.add_handler(CommandHandler("give",cmd_give))
    app.add_handler(CommandHandler("sgive",cmd_sgive))
    app.add_handler(CommandHandler("gsend",cmd_gsend))
    app.add_handler(CommandHandler("ginfo",cmd_ginfo))
    app.add_handler(CommandHandler(list(GIVEAWAY_ITEMS),cmd_giveaway))
    app.add_handler(CommandHandler("change",cmd_change))
    app.add_handler(CommandHandler("tgeroy",cmd_tgeroy))
    app.add_handler(CommandHandler(["top","top1","top7","top30"],cmd_rating_top))
    app.add_handler(CommandHandler(["gtop","gtop1","gtop7","gtop30"],cmd_gtop))
    app.add_handler(CommandHandler(["boylar","gboylar"],cmd_boylar))
    app.add_handler(CommandHandler("eboylar",cmd_eboylar))
    app.add_handler(CommandHandler(["tchat","tchat1","tchat7","tchat30","tchats"],cmd_tchat))
    app.add_handler(CommandHandler("stats",cmd_market_stats))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,successful_payment))
    app.add_handler(CommandHandler("tep",cmd_tep))
    app.add_handler(CommandHandler("profile",cmd_profile))
    app.add_handler(CommandHandler("market",cmd_market))
    app.add_handler(CommandHandler("admin",cmd_admin))
    # Admin panel callbacks and hard block guards run before normal handlers.
    app.add_handler(MessageHandler(filters.ALL, admin_guard_message), group=-100)
    app.add_handler(CallbackQueryHandler(admin_guard_callback), group=-100)
    # During a game, messages the chat's write rule forbids are deleted before anything else sees them.
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_write_guard), group=-90)
    app.add_handler(CommandHandler("aktiv",cmd_aktiv))
    app.add_handler(CommandHandler("unaktiv",cmd_unaktiv))
    app.add_handler(CommandHandler("block",cmd_block))
    app.add_handler(CommandHandler("unblock",cmd_unblock))
    app.add_handler(CommandHandler("gblock",cmd_gblock))
    app.add_handler(CommandHandler("ungblock",cmd_gunblock))
    app.add_handler(CommandHandler("checkuser",cmd_checkuser))
    app.add_handler(CommandHandler("inventory",cmd_inventory))
    app.add_handler(CommandHandler("pul",cmd_pul))
    app.add_handler(CommandHandler("olmos",cmd_olmos))
    app.add_handler(CommandHandler("coin",cmd_coin))
    app.add_handler(CommandHandler("sdiamond",cmd_sdiamond))
    app.add_handler(CommandHandler("smoney",cmd_smoney))
    app.add_handler(CommandHandler("scoin",cmd_scoin))
    app.add_handler(CommandHandler("sgeroy",cmd_sgeroy))
    app.add_handler(CommandHandler("rgeroy",cmd_rgeroy))
    app.add_handler(CommandHandler("bust",cmd_bust))
    app.add_handler(CommandHandler("bust1",cmd_bust1))
    app.add_handler(CommandHandler("bust2",cmd_bust2))
    app.add_handler(CommandHandler("fullbust",cmd_fullbust))
    app.add_handler(CommandHandler("gbust",cmd_gbust))
    app.add_handler(CommandHandler("you",cmd_you))
    app.add_handler(CommandHandler("gunblock",cmd_gunblock))
    app.add_handler(CommandHandler("blocks",cmd_blocks))
    app.add_handler(CommandHandler("id",cmd_id))
    app.add_handler(CommandHandler("gsearch",cmd_gsearch))
    app.add_handler(CommandHandler("groups",cmd_groups))
    app.add_handler(CommandHandler("active",cmd_active_games))
    app.add_handler(CommandHandler("checkgaming",cmd_checkgaming))
    app.add_handler(CommandHandler("stopgames",cmd_stopgames))
    app.add_handler(CommandHandler("geroys",cmd_heroes))
    app.add_handler(CommandHandler("rgm",cmd_rgm))
    app.add_handler(CommandHandler("vip",cmd_vip))
    app.add_handler(CommandHandler("unvip",cmd_unvip))
    app.add_handler(CommandHandler("broadcast",cmd_broadcast))
    app.add_handler(CommandHandler("zapravka1",cmd_zapravka1))
    app.add_handler(CommandHandler("zapravka7",cmd_zapravka7))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(cb_active_role, pattern=r"^ar:"))
    app.add_handler(CallbackQueryHandler(cb_join,r"^join:"))
    app.add_handler(CallbackQueryHandler(cb_mode,r"^mode:"))
    app.add_handler(CallbackQueryHandler(cb_action,r"^act:"))
    app.add_handler(CallbackQueryHandler(cb_manip2,r"^manip2:"))
    app.add_handler(CallbackQueryHandler(cb_amode,r"^amode:"))
    app.add_handler(CallbackQueryHandler(cb_kon,r"^kon:"))
    app.add_handler(CallbackQueryHandler(cb_card,r"^card:"))
    app.add_handler(CallbackQueryHandler(cb_hang,r"^hang:"))
    app.add_handler(CallbackQueryHandler(cb_afs,r"^afs:"))
    app.add_handler(CallbackQueryHandler(cb_settings,r"^cset:"))
    app.add_handler(CallbackQueryHandler(cb_para,r"^para:"))
    app.add_handler(CallbackQueryHandler(cb_eco,r"^eco:"))
    app.add_handler(CallbackQueryHandler(cb_giveaway,r"^gw:"))
    app.add_handler(CallbackQueryHandler(cb_lottery,r"^lot:"))
    app.add_handler(CallbackQueryHandler(ignore_button,r"^ignore$"))
    app.add_handler(CallbackQueryHandler(cb_res,r"^res:"))
    app.add_handler(CallbackQueryHandler(cb_zombie,r"^zombie:"))
    app.add_handler(CallbackQueryHandler(cb_katani_mode,r"^katani_mode:"))
    app.add_handler(CallbackQueryHandler(cb_katani,r"^katani:"))
    app.add_handler(CallbackQueryHandler(cb_prof,r"^prof:"))
    app.add_handler(CallbackQueryHandler(cb_prof_target,r"^prof_target:"))
    app.add_handler(CallbackQueryHandler(cb_vey1,r"^vey1:"))
    app.add_handler(CallbackQueryHandler(cb_vey2,r"^vey2:"))
    app.add_handler(CallbackQueryHandler(cb_menu,r"^menu:"))
    app.add_handler(CallbackQueryHandler(cb_role,r"^role:\d+$"))
    app.add_handler(CallbackQueryHandler(hero_callback,r"^hero:"))
    app.add_handler(CallbackQueryHandler(cb_heroact,r"^heroact:"))
    app.add_handler(CallbackQueryHandler(cb_buy,r"^buy:"))
    # A pending profile-swap id is consumed here and stops further private-text handlers.
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, swap_id_text), group=0)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, admin_text_handler), group=1)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, hero_private_text), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, private_game_text), group=3)
    app.add_handler(CallbackQueryHandler(cb_vote,r"^(vote|skip):"))
    app.add_handler(CallbackQueryHandler(cb_af,r"^af:"))
    app.add_handler(CallbackQueryHandler(cb_folbin_msg,r"^(read_f|cancel_f):"))
    app.add_error_handler(error_handler)
