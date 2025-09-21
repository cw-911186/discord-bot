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
        logging.info("-" * 20)
        
        # 채널 ID들을 봇 객체에 등록
        self.welcome_channel_id = WELCOME_CHANNEL_ID
        self.nickname_channel_id = NICKNAME_CHANNEL_ID
        self.role_channel_id = ROLE_CHANNEL_ID
        self.party_text_channel_id = PARTY_TEXT_CHANNEL_ID
        self.party_trigger_channel_id = PARTY_TRIGGER_CHANNEL_ID

    async def on_error(self, event, *args, **kwargs):
        logging.error(f'이벤트 {event}에서 오류 발생', exc_info=True)

# ----------------- 봇 실행 -----------------
if __name__ == '__main__':
    if not BOT_TOKEN:
        logging.error("❌ DISCORD_BOT_TOKEN 환경변수가 설정되지 않았습니다!")
        exit(1)
    
    # 봇 실행 (keep_alive 제거됨)
    bot = MyBot()
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        logging.error(f"봇 실행 중 오류 발생: {e}")