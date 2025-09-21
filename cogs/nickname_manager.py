import discord
from discord.ext import commands
from discord import ui, app_commands

# 닉네임 변경 모달 (팝업 창)
class NicknameModal(ui.Modal, title="닉네임 변경"):
    custom_nickname = ui.TextInput(label="별명", placeholder="예: 홍길동", required=True)
    birth_year = ui.TextInput(label="출생년도 뒷 2자리", placeholder="예: 99", min_length=2, max_length=2, required=True)
    lol_nickname = ui.TextInput(label="롤 닉네임", placeholder="예: Hide on bush#KR1", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        new_nickname = f"{self.custom_nickname.value}/{self.birth_year.value}/{self.lol_nickname.value}"
        try:
            await interaction.user.edit(nick=new_nickname)
            await interaction.response.send_message(f"✅ 닉네임이 '{new_nickname}'(으)로 성공적으로 변경되었습니다.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ 봇의 권한이 부족하여 닉네임을 변경할 수 없습니다.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 오류가 발생했습니다: {e}", ephemeral=True)

# 닉네임 변경 버튼 View
class NicknameButtonView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="닉네임 변경하기", style=discord.ButtonStyle.green, custom_id="nickname_change_button")
    async def change_nickname_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(NicknameModal())

# Cog 클래스 정의
class NicknameManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 봇이 재시작되어도 버튼이 동작하도록 View를 추가합니다.
        # Cog에서는 setup_hook 대신 __init__에서 처리하는 것이 일반적입니다.
        self.bot.add_view(NicknameButtonView())


    # 닉네임 변경 버튼 설치 명령어
    @app_commands.command(name="닉네임변경_버튼설치", description="'닉네임-변경' 채널에 안내 메시지와 버튼을 설치합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_nickname_channel(self, interaction: discord.Interaction):
        if interaction.channel.id != self.bot.nickname_channel_id:
            await interaction.response.send_message(f"이 명령어는 <#{self.bot.nickname_channel_id}> 채널에서만 사용할 수 있습니다.", ephemeral=True)
            return

        setup_embed = discord.Embed(
            title="📝 닉네임 변경 안내",
            description="서버 활동을 위해서는 닉네임 변경이 필요합니다.\n\n"
                        "**닉네임 형식:** `별명 / 출생년도 / 롤 닉네임`\n\n"
                        "아래의 **'닉네임 변경하기'** 버튼을 눌러 정보를 입력해주세요.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=setup_embed, view=NicknameButtonView())
        await interaction.response.send_message("✅ 닉네임 변경 안내 버튼을 성공적으로 설치했습니다.", ephemeral=True)

# Cog를 봇에 추가하기 위한 필수 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(NicknameManager(bot))
