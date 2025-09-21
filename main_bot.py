import discord
from discord.ext import commands
import os
import logging

# ----------------- 로깅 설정 -----------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# ----------------- 보안 설정 -----------------
# 허용된 서버 ID만 명시 (본인 서버 ID로 변경하세요)
ALLOWED_GUILDS = [int(os.getenv('ALLOWED_GUILD_ID', '0'))]  # 실제 서버 ID로 교체 필요

# ----------------- 봇 설정 -----------------
# 환경변수에서 봇 토큰 가져오기
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# 채널 ID들 (환경변수로도 설정 가능)
WELCOME_CHANNEL_ID = int(os.getenv('WELCOME_CHANNEL_ID', '1418458446864449541'))
NICKNAME_CHANNEL_ID = int(os.getenv('NICKNAME_CHANNEL_ID', '1418458447246262275'))
ROLE_CHANNEL_ID = int(os.getenv('ROLE_CHANNEL_ID', '1418630139876737066'))
PARTY_TEXT_CHANNEL_ID = int(os.getenv('PARTY_TEXT_CHANNEL_ID', '1419014874645659708'))
PARTY_TRIGGER_CHANNEL_ID = int(os.getenv('PARTY_TRIGGER_CHANNEL_ID', '1419015107576463380'))

# ----------------- 봇 클래스 정의 -----------------
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"✅ Cog 로드 성공: {filename}")
                except Exception as e:
                    logging.error(f"❌ Cog 로드 실패: {filename} | {e}")
        
        try:
            synced = await self.tree.sync()
            logging.info(f"✅ {len(synced)}개의 슬래시 커맨드 동기화 완료")
        except Exception as e:
            logging.error(f"❌ 슬래시 커맨드 동기화 실패: {e}")

    async def on_ready(self):
        logging.info(f"{self.user}으로 로그인 성공!")
        logging.info(f"봇 ID: {self.user.id}")
        logging.info(f"허용된 서버 수: {len(ALLOWED_GUILDS)}")
        logging.info("-" * 20)
        
        # 현재 참여 중인 서버 검사
        for guild in self.guilds:
            if guild.id not in ALLOWED_GUILDS:
                logging.warning(f"⚠️ 허용되지 않은 서버 발견: {guild.name} (ID: {guild.id})")
                await guild.leave()
                logging.info(f"🚪 서버에서 자동 탈퇴: {guild.name}")
        
        # 채널 ID들을 봇 객체에 등록
        self.welcome_channel_id = WELCOME_CHANNEL_ID
        self.nickname_channel_id = NICKNAME_CHANNEL_ID
        self.role_channel_id = ROLE_CHANNEL_ID
        self.party_text_channel_id = PARTY_TEXT_CHANNEL_ID
        self.party_trigger_channel_id = PARTY_TRIGGER_CHANNEL_ID

    async def on_guild_join(self, guild):
        """새 서버에 추가되었을 때 허용 여부 확인"""
        if guild.id not in ALLOWED_GUILDS:
            logging.warning(f"🚫 허용되지 않은 서버 초대 거부: {guild.name} (ID: {guild.id})")
            await guild.leave()
            logging.info(f"🚪 서버에서 즉시 탈퇴: {guild.name}")
        else:
            logging.info(f"✅ 허용된 서버에 참여: {guild.name} (ID: {guild.id})")

    async def on_error(self, event, *args, **kwargs):
        logging.error(f'이벤트 {event}에서 오류 발생', exc_info=True)

    async def on_command_error(self, ctx, error):
        """명령어 오류 처리"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ 이 명령어를 사용할 권한이 없습니다.")
        elif isinstance(error, commands.CommandNotFound):
            # 존재하지 않는 명령어는 무시
            pass
        else:
            logging.error(f"명령어 오류: {error}")

# ----------------- 봇 실행 -----------------
if __name__ == '__main__':
    if not BOT_TOKEN:
        logging.error("❌ DISCORD_BOT_TOKEN 환경변수가 설정되지 않았습니다!")
        exit(1)
    
    if not ALLOWED_GUILDS or ALLOWED_GUILDS == [YOUR_SERVER_ID_HERE]:
        logging.error("❌ ALLOWED_GUILDS에 실제 서버 ID를 설정해주세요!")
        exit(1)
    
    # 봇 실행
    bot = MyBot()
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        logging.error(f"봇 실행 중 오류 발생: {e}")