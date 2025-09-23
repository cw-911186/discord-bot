import discord
from discord.ext import commands
from discord import ui, app_commands

# 서버 소유자 전용 데코레이터
def owner_only():
    async def predicate(interaction):
        return interaction.user.id == interaction.guild.owner_id
    return app_commands.check(predicate)

# 역할 목록 (서버에 생성된 역할 이름과 정확히 일치해야 합니다)
PLAY_TIME_ROLES = ["Morning", "Afternoon", "Night", "Dawn", "All-TIME"]

# 역할 선택 버튼 View
class RoleSelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # 버튼 클릭 시 실행될 공통 콜백 함수
    async def role_callback(self, interaction: discord.Interaction, role_name: str):
        # 클릭한 유저와 서버(길드) 정보를 가져옵니다.
        member = interaction.user
        guild = interaction.guild

        # 서버에 해당 이름의 역할이 있는지 확인합니다.
        role_to_add = discord.utils.get(guild.roles, name=role_name)
        if not role_to_add:
            await interaction.response.send_message(f"⚠️ '{role_name}' 역할을 찾을 수 없습니다. 서버 관리자에게 문의하세요.", ephemeral=True)
            return

        try:
            # 1. 유저가 이미 가지고 있는 플레이 시간 역할들을 모두 제거합니다.
            roles_to_remove = [role for role in member.roles if role.name in PLAY_TIME_ROLES]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="시간대 역할 변경")

            # 2. 새로 선택한 역할을 부여합니다.
            await member.add_roles(role_to_add, reason="시간대 역할 선택")
            await interaction.response.send_message(f"✅ '{role_name}' 역할이 성공적으로 부여되었습니다.", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ 봇의 권한이 부족하여 역할을 변경할 수 없습니다. 봇의 역할이 부여할 역할보다 높은지 확인하세요.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 오류가 발생했습니다: {e}", ephemeral=True)

    # 각 역할에 대한 버튼 생성
    @ui.button(label="Morning", style=discord.ButtonStyle.secondary, custom_id="role_morning")
    async def morning_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.role_callback(interaction, "Morning")

    @ui.button(label="Afternoon", style=discord.ButtonStyle.secondary, custom_id="role_afternoon")
    async def afternoon_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.role_callback(interaction, "Afternoon")

    @ui.button(label="Night", style=discord.ButtonStyle.secondary, custom_id="role_night")
    async def night_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.role_callback(interaction, "Night")

    @ui.button(label="Dawn", style=discord.ButtonStyle.secondary, custom_id="role_dawn")
    async def dawn_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.role_callback(interaction, "Dawn")
    
    @ui.button(label="All-TIME", style=discord.ButtonStyle.primary, custom_id="role_all_time")
    async def all_time_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.role_callback(interaction, "All-TIME")

# Cog 클래스 정의
class RoleManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(RoleSelectView())

    # 역할 변경 버튼 설치 명령어 - 서버 소유자 전용
    @app_commands.command(name="역할변경_버튼설치", description="'역할-변경' 채널에 안내 메시지와 버튼을 설치합니다. (서버 소유자 전용)")
    @owner_only()
    async def setup_role_channel(self, interaction: discord.Interaction):
        if interaction.channel.id != self.bot.role_channel_id:
            await interaction.response.send_message(f"이 명령어는 <#{self.bot.role_channel_id}> 채널에서만 사용할 수 있습니다.", ephemeral=True)
            return

        setup_embed = discord.Embed(
            title="🕰️ 활동 시간 역할 변경",
            description="주로 활동하는 시간대를 선택하거나 변경할 수 있습니다.\n\n"
                        "역할을 변경하면 기존에 있던 시간대 역할은 사라지고 새로 선택한 역할이 부여됩니다.",
            color=discord.Color.orange()
        )
        await interaction.channel.send(embed=setup_embed, view=RoleSelectView())
        await interaction.response.send_message("✅ 역할 변경 안내 버튼을 성공적으로 설치했습니다.", ephemeral=True)

# Cog를 봇에 추가하기 위한 필수 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(RoleManager(bot))