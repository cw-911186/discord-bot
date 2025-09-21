import discord
from discord.ext import commands
from discord import ui

# 역할 목록 (role_manager.py와 동일하게 유지)
PLAY_TIME_ROLES = ["Morning", "Afternoon", "Night", "Dawn", "All-TIME"]

# --- 2단계: 역할 선택 View ---
class RoleSelectViewForOnboarding(ui.View):
    def __init__(self, original_interaction: discord.Interaction):
        super().__init__(timeout=180.0) # 3분 동안만 상호작용 가능
        self.original_interaction = original_interaction

    async def on_timeout(self):
        # 타임아웃되면 버튼 비활성화
        for item in self.children:
            item.disabled = True
        timeout_embed = self.original_interaction.message.embeds[0]
        timeout_embed.set_footer(text="시간이 초과되었습니다. 역할 변경은 #역할-변경 채널을 이용해주세요.")
        await self.original_interaction.edit_original_response(embed=timeout_embed, view=self)

    async def role_callback(self, interaction: discord.Interaction, role_name: str):
        member = interaction.user
        guild = interaction.guild
        role_to_add = discord.utils.get(guild.roles, name=role_name)
        
        if not role_to_add:
            return await interaction.response.send_message(f"⚠️ '{role_name}' 역할을 찾을 수 없습니다.", ephemeral=True)

        try:
            roles_to_remove = [role for role in member.roles if role.name in PLAY_TIME_ROLES]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)
            await member.add_roles(role_to_add)

            # 역할 부여 후 최종 완료 메시지로 수정
            final_embed = discord.Embed(
                title="✅ 온보딩 완료!",
                description=f"{member.mention}님, 서버에 오신 것을 환영합니다!\n\n"
                            f"모든 기본 설정이 완료되었습니다. 이제 서버의 모든 채널을 자유롭게 이용하실 수 있습니다.",
                color=discord.Color.green()
            )
            # 모든 버튼 비활성화
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=final_embed, view=self)

        except Exception as e:
            await interaction.response.send_message(f"⚠️ 오류가 발생했습니다: {e}", ephemeral=True)

    # 역할 버튼들
    @ui.button(label="Morning", style=discord.ButtonStyle.secondary)
    async def morning(self, i: discord.Interaction, b: ui.Button): await self.role_callback(i, b.label)
    @ui.button(label="Afternoon", style=discord.ButtonStyle.secondary)
    async def afternoon(self, i: discord.Interaction, b: ui.Button): await self.role_callback(i, b.label)
    @ui.button(label="Night", style=discord.ButtonStyle.secondary)
    async def night(self, i: discord.Interaction, b: ui.Button): await self.role_callback(i, b.label)
    @ui.button(label="Dawn", style=discord.ButtonStyle.secondary)
    async def dawn(self, i: discord.Interaction, b: ui.Button): await self.role_callback(i, b.label)
    @ui.button(label="All-TIME", style=discord.ButtonStyle.primary)
    async def all_time(self, i: discord.Interaction, b: ui.Button): await self.role_callback(i, b.label)


# --- 1단계: 닉네임 변경 모달 ---
class OnboardingNicknameModal(ui.Modal, title="1단계: 닉네임 설정"):
    custom_nickname = ui.TextInput(label="별명", placeholder="예: 홍길동", required=True)
    birth_year = ui.TextInput(label="출생년도 뒷 2자리", placeholder="예: 99", min_length=2, max_length=2, required=True)
    lol_nickname = ui.TextInput(label="롤 닉네임", placeholder="예: Hide on bush#KR1", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        new_nickname = f"{self.custom_nickname.value}/{self.birth_year.value} / {self.lol_nickname.value}"
        try:
            await interaction.user.edit(nick=new_nickname)
            # 닉네임 변경 성공 후, 2단계(역할 부여)로 전환
            await interaction.response.send_message(f"✅ 닉네임이 '{new_nickname}'(으)로 설정되었습니다. 다음 단계를 진행해주세요.", ephemeral=True)
            
            # 기존 메시지를 2단계 안내로 수정
            role_embed = discord.Embed(
                title="➡️ 2단계: 활동 시간 역할 선택",
                description=f"주로 활동하시는 시간대를 선택하여 역할을 받아주세요!\n\n"
                            f"이 역할은 다른 사람들과의 파티 시간 조율에 도움이 됩니다.",
                color=discord.Color.gold()
            )
            # 원본 메시지를 수정하기 위해 interaction.message를 사용
            await interaction.message.edit(embed=role_embed, view=RoleSelectViewForOnboarding(interaction))
            
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 오류가 발생했습니다: {e}", ephemeral=True)


# --- 1단계: 닉네임 변경 View ---
class OnboardingView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 환영 메시지는 계속 떠 있어야 하므로 타임아웃 없음

    @ui.button(label="닉네임 변경하기", style=discord.ButtonStyle.green, custom_id="onboarding_nickname_button")
    async def change_nickname(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(OnboardingNicknameModal())


# --- Cog 클래스 ---
class OnboardingManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 봇 재시작 시에도 온보딩 버튼이 동작하도록 View 등록
        if not hasattr(bot, 'added_onboarding_view'):
            self.bot.add_view(OnboardingView())
            bot.added_onboarding_view = True

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self.bot.get_channel(self.bot.welcome_channel_id)
        if channel:
            embed = discord.Embed(
                title=f"🎉 {member.guild.name} 서버에 오신 것을 환영합니다!",
                description=f"{member.mention}님, 안녕하세요!\n\n"
                            f"서버 활동을 위해 **2단계 설정**이 필요합니다.\n\n"
                            f"**➡️ 1단계: 닉네임 변경**\n"
                            f"아래 버튼을 눌러 `별명 / 출생년도 / 롤 닉네임` 형식으로 설정해주세요.",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await channel.send(embed=embed, view=OnboardingView())

async def setup(bot: commands.Bot):
    await bot.add_cog(OnboardingManager(bot))
