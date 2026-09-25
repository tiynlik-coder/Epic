"""Profile text building."""

import html
import time

from config import CHANNEL_USERNAME, EMOJI, SHOP_ITEMS, WIN_REWARD
from models.admin_data import active_roles_for
from models.economy import disabled_items, vip_until
from models.users import get_user, inv
from utils.telegram_utils import is_epic_channel_member


def stylized_name(name: str) -> str:
    """Render Latin names in the requested bold-italic serif style."""
    upper = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁"))
    lower = dict(zip("abcdefghijklmnopqrstuvwxyz", "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"))
    return "".join(upper.get(ch, lower.get(ch, ch)) for ch in (name or "Nomsiz"))


def profile_text(uid):
    r=get_user(uid); d=inv(uid); off=disabled_items(uid)
    name=stylized_name(str(r['first_name'] or 'Nomsiz')) if r else stylized_name('Nomsiz')
    until=vip_until(uid)
    vip="" if until is None else " ⭐️ VIP" + ("" if until==0 else f" ({max(0,int((until-time.time())//86400))} kun)")
    lines=[
        f"<b>{html.escape(name)}</b>{vip}",
        "",
        f"💵 <b>Pullar:</b> {int(r['money'] or 0)}" if r else "💵 <b>Pullar:</b> 0",
        f"💎 <b>Olmos:</b> {int(r['diamonds'] or 0)}" if r else "💎 <b>Olmos:</b> 0",
        f"🪙 <b>Epic Coin:</b> {int(r['coins'] or 0)}" if r else "🪙 <b>Epic Coin:</b> 0",
        "",
        *[f"{label}: {d.get(key,0)}"+(" (o‘chirilgan)" if key in off else "") for key,(label,_,_) in SHOP_ITEMS.items()],
        "",
        f"🎲 <b>Barcha o‘yinlar:</b> {int(r['games'] or 0) if r else 0}",
        f"🎯 <b>G‘alaba:</b> {int(r['wins'] or 0) if r else 0}",
    ]
    rows=active_roles_for(uid)
    if rows:
        lines.append('🃏 <b>Faol rollar:</b>')
        lines.extend(f"{EMOJI.get(r[1],'🎭')} {html.escape(r[1])}" for r in rows)
    else: lines.append('🃏 <b>Faol rollar:</b> 0')
    return "\n".join(lines)


async def build_profile_text(bot, uid: int) -> str:
    text = profile_text(uid)
    if CHANNEL_USERNAME and not await is_epic_channel_member(bot, uid):
        text += f"\n\nKanalga obuna bo‘lsangiz g‘alaba uchun 2x mukofot ({WIN_REWARD*2}💷) olasiz!\nKanal {CHANNEL_USERNAME}"
    return text


def active_role_text(uid):
    rows=active_roles_for(uid)
    if not rows: current="🃏 Faol rollar: yo‘q"
    else: current="🃏 <b>Faol rollar:</b>\n"+"\n".join(f"• {EMOJI.get(r[1],'🎭')} {html.escape(r[1])}" for r in rows)
    return "🎭 <b>Faol rol</b>\n\nSotib olingan rol keyingi mos o‘yinda birinchi navbatda beriladi.\n\n"+current
