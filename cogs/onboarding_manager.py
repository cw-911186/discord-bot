import discord
from discord.ext import commands
from discord import ui
import asyncio

# 역할 목록
PLAY_TIME_ROLES = ["Morning", "Afternoon", "Night", "Dawn", "All-TIME"]
VERIFIED_ROLE_NAME = "인증완료"

# 서버 소유자 전용 데코레이터
def owner_only():
    async def predicate(ctx):
        return ctx.author.id == ctx.guild.owner_id
    return commands.check(predicate)

# --- 2단계: 역할 선택 View (개인 스레드용) ---
class PrivateRoleSelectView(ui.View):
    def __init__(self, thread, member):
        super().__init__(timeout=300.0)
        self.thread = thread
        self.member = member

    async def on_timeout(self):
        embed = discord.Embed(
            title="⏰ 시간 초과",
            description="온보딩 시간이 초과되었습니다.\n서버 관리자에게 문의하거나 다시 서버에 입장해주세요.",
            color=discord.Color.red()
        )
        await self.thread.send(embed=embed)

    async def role_callback(self, interaction: discord.Interaction, role_name: str):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("본인의 온보딩만 진행할 수 있습니다.", ephemeral=True)
            return

        guild = interaction.guild
        role_to_add = discord.utils.get(guild.roles, name=role_name)
        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        
        if not role_to_add or not verified_role:
            await interaction.response.send_message(f"역할을 찾을 수 없습니다. 서버 관리자에게 문의하세요.", ephemeral=True)
            return

        try:
            # 기존 시간대 역할 제거 후 새 역할 부여
            roles_to_remove = [role for role in self.member.roles if role.name in PLAY_TIME_ROLES]
            if roles_to_remove:
                await self.member.remove_roles(*roles_to_remove)
            
            # 선택한 시간대 역할과 인증완료 역할 부여
            await self.member.add_roles(role_to_add, verified_role)

            # 온보딩 완료 메시지
            final_embed = discord.Embed(
                title="✅ 온보딩 완료!",
                description=f"{self.member.mention}님의 서버 설정이 모두 완료되었습니다!\n\n"
                            f"**설정된 정보:**\n"
                            f"• 닉네임: {self.member.display_name}\n"
                            f"• 활동 시간: {role_name}\n\n"
                            f"이제 서버의 모든 채널을 자유롭게 이용하실 수 있습니다.",
                color=discord.Color.green()
            )
            
            for item in self.children:
                item.disabled = True
                
            await interaction.response.edit_message(embed=final_embed, view=self)

            # 환영 채널에 완료 메시지 전송
            bot = interaction.client
            welcome_channel = bot.get_channel(bot.welcome_channel_id)
            if welcome_channel:
                welcome_embed = discord.Embed(
                    title="🎉 새로운 멤버를 환영합니다!",
                    description=f"{self.member.mention}님이 서버에 입장하셨습니다!\n\n"
                                f"**닉네임:** {self.member.display_name}\n"
                                f"**활동 시간:** {role_name}",
                    color=discord.Color.blue()
                )
                welcome_embed.set_thumbnail(url=self.member.display_avatar.url)
                await welcome_channel.send(embed=welcome_embed)

            # 3초 후 스레드 삭제
            await asyncio.sleep(3)
            try:
                await self.thread.delete()
            except:
                pass

        except Exception as e:
            await interaction.response.send_message(f"오류가 발생했습니다: {e}", ephemeral=True)

    # 역할 버튼들
    @ui.button(label="Morning", style=discord.ButtonStyle.secondary)
    async def morning(self, i: discord.Interaction, b: ui.Button): 
        await self.role_callback(i, b.label)
    
    @ui.button(label="Afternoon", style=discord.ButtonStyle.secondary)
    async def afternoon(self, i: discord.Interaction, b: ui.Button): 
        await self.role_callback(i, b.label)
    
    @ui.button(label="Night", style=discord.ButtonStyle.secondary)
    async def night(self, i: discord.Interaction, b: ui.Button): 
        await self.role_callback(i, b.label)
    
    @ui.button(label="Dawn", style=discord.ButtonStyle.secondary)
    async def dawn(self, i: discord.Interaction, b: ui.Button): 
        await self.role_callback(i, b.label)
    
    @ui.button(label="All-TIME", style=discord.ButtonStyle.primary)
    async def all_time(self, i: discord.Interaction, b: ui.Button): 
        await self.role_callback(i, b.label)


# --- 1단계: 닉네임 변경 모달 (개인 스레드용) ---
class PrivateNicknameModal(ui.Modal, title="1단계: 닉네임 설정"):
    custom_nickname = ui.TextInput(label="별명", placeholder="예: 홍길동", required=True)
    birth_year = ui.TextInput(label="출생년도 뒷 2자리", placeholder="예: 99", min_length=2, max_length=2, required=True)
    lol_nickname = ui.TextInput(
        label="롤 닉네임 [#태그필수!]", 
        placeholder="예: Hide on bush#KR1 (반드시 #태그 포함!)", 
        required=True
    )

    def __init__(self, thread, member):
        super().__init__()
        self.thread = thread
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("본인의 온보딩만 진행할 수 있습니다.", ephemeral=True)
            return

        # 태그 검증 추가
        if '#' not in self.lol_nickname.value:
            await interaction.response.send_message(
                "❌ **롤 닉네임에 #태그가 누락되었습니다!**\n\n"
                "올바른 형식: `닉네임#태그`\n"
                "예시: `Hide on bush#KR1`\n\n"
                "다시 버튼을 눌러 정확하게 입력해주세요.", 
                ephemeral=True
            )
            return

        new_nickname = f"{self.custom_nickname.value}/{self.birth_year.value}/{self.lol_nickname.value}"
        
        try:
            await self.member.edit(nick=new_nickname)
            
            await interaction.response.send_message(f"✅ 닉네임이 '{new_nickname}'으로 설정되었습니다!", ephemeral=True)
            
            role_embed = discord.Embed(
                title="➡️ 2단계: 활동 시간 역할 선택",
                description=f"주로 활동하시는 시간대를 선택하여 역할을 받아주세요!\n\n"
                            f"이 역할은 다른 사람들과의 파티 시간 조율에 도움이 됩니다.",
                color=discord.Color.gold()
            )
            
            await self.thread.send(embed=role_embed, view=PrivateRoleSelectView(self.thread, self.member))
            
        except Exception as e:
            await int

# --- 1단계: 닉네임 변경 View (개인 스레드용) ---
class PrivateOnboardingView(ui.View):
    def __init__(self, thread, member):
        super().__init__(timeout=300.0)
        self.thread = thread
        self.member = member

    async def on_timeout(self):
        embed = discord.Embed(
            title="⏰ 시간 초과",
            description="온보딩 시간이 초과되었습니다.\n서버 관리자에게 문의하거나 다시 서버에 입장해주세요.",
            color=discord.Color.red()
        )
        await self.thread.send(embed=embed)

    @ui.button(label="닉네임 설정하기", style=discord.ButtonStyle.green, custom_id="private_nickname_button")
    async def change_nickname(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("본인의 온보딩만 진행할 수 있습니다.", ephemeral=True)
            return
        
        await interaction.response.send_modal(PrivateNicknameModal(self.thread, self.member))


# --- Cog 클래스 ---
class ImprovedOnboardingManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """멤버 입장 시 개인 온보딩 스레드 생성"""
        welcome_channel = self.bot.get_channel(self.bot.welcome_channel_id)
        if not welcome_channel:
            return

        try:
            thread = await welcome_channel.create_thread(
                name=f"{member.display_name}님의 온보딩",
                type=discord.ChannelType.private_thread,
                auto_archive_duration=60
            )
            
            await thread.add_user(member)
            
            embed = discord.Embed(
                title=f"🎉 {member.guild.name} 서버에 오신 것을 환영합니다!",
                description=f"{member.mention}님, 안녕하세요!\n\n"
                        f"이 스레드는 **당신만을 위한 개인 공간**입니다.\n"
                        f"서버 활동을 위해 **2단계 설정**을 완료해주세요.\n\n"
                        f"**⚠️ 중요:** 온보딩 완료 전까지는 다른 채널을 사용할 수 없습니다.\n\n"
                        f"**➡️ 1단계: 닉네임 설정**\n"
                        f"형식: `별명/출생년도/롤닉네임#태그`\n"
                        f"**🔥 주의: #태그를 반드시 포함하세요!**\n"
                        f"예시: `홍길동/99/Hide on bush#KR1`",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="이 과정은 5분 내에 완료해주세요.")
            
            await thread.send(embed=embed, view=PrivateOnboardingView(thread, member))
            
        except Exception as e:
            print(f"온보딩 스레드 생성 실패: {e}")
            embed = discord.Embed(
                title="⚠️ 온보딩 설정 필요",
                description=f"{member.mention}님, 서버 활동을 위해 닉네임 설정과 역할 선택이 필요합니다.\n"
                            f"서버 관리자에게 문의해주세요.",
                color=discord.Color.orange()
            )
            await welcome_channel.send(embed=embed, delete_after=30)

    @commands.command(name="역할생성")
    @owner_only()
    async def create_roles(self, ctx):
        """필요한 역할들을 자동으로 생성 (서버 소유자 전용)"""
        guild = ctx.guild
        roles_to_create = PLAY_TIME_ROLES + [VERIFIED_ROLE_NAME]
        created_roles = []
        
        for role_name in roles_to_create:
            existing_role = discord.utils.get(guild.roles, name=role_name)
            if not existing_role:
                try:
                    # 인증완료 역할은 일반 멤버 권한으로 생성
                    permissions = discord.Permissions.none()
                    permissions.update(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        connect=True,
                        speak=True,
                        use_voice_activation=True
                    )
                    
                    color = discord.Color.light_grey() if role_name == VERIFIED_ROLE_NAME else discord.Color.default()
                    new_role = await guild.create_role(
                        name=role_name, 
                        color=color,
                        permissions=permissions if role_name == VERIFIED_ROLE_NAME else discord.Permissions.none()
                    )
                    created_roles.append(role_name)
                except Exception as e:
                    await ctx.send(f"'{role_name}' 역할 생성 실패: {e}")
                    
        if created_roles:
            await ctx.send(f"✅ 다음 역할들이 생성되었습니다: {', '.join(created_roles)}")
        else:
            await ctx.send("모든 필요한 역할이 이미 존재합니다.")

    @commands.command(name="권한설정")
    @owner_only()
    async def setup_permissions(self, ctx):
        """채널 권한을 설정 (서버 소유자 전용)"""
        guild = ctx.guild
        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        everyone_role = guild.default_role
        
        if not verified_role:
            await ctx.send(f"'{VERIFIED_ROLE_NAME}' 역할이 존재하지 않습니다. `!역할생성` 명령어를 먼저 실행하세요.")
            return
        
        updated_channels = []
        
        # 일반 채널들에 대해 권한 설정 (관리자 전용 채널 제외)
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                try:
                    # 환영 채널과 관리자 전용 채널은 제외
                    if (channel.id == self.bot.welcome_channel_id or 
                        "관리" in channel.name.lower() or 
                        "admin" in channel.name.lower() or
                        channel.overwrites_for(guild.owner).administrator):
                        continue
                    
                    # @everyone은 채널 보기 불가
                    await channel.set_permissions(everyone_role, view_channel=False)
                    # 인증완료 역할은 기본 권한만
                    await channel.set_permissions(verified_role, 
                                                view_channel=True, 
                                                send_messages=True, 
                                                read_message_history=True,
                                                connect=True if isinstance(channel, discord.VoiceChannel) else None,
                                                speak=True if isinstance(channel, discord.VoiceChannel) else None)
                    updated_channels.append(channel.name)
                    
                except Exception as e:
                    await ctx.send(f"'{channel.name}' 채널 권한 설정 실패: {e}")
        
        await ctx.send(f"✅ {len(updated_channels)}개 채널의 권한이 설정되었습니다.\n"
                       f"'{VERIFIED_ROLE_NAME}' 역할로 일반 채널 접근이 가능합니다.")

    @commands.command(name="권한초기화")
    @owner_only()
    async def reset_verified_role_permissions(self, ctx):
        """인증완료 역할의 권한을 안전하게 초기화 (서버 소유자 전용)"""
        guild = ctx.guild
        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        
        if not verified_role:
            await ctx.send(f"'{VERIFIED_ROLE_NAME}' 역할이 존재하지 않습니다.")
            return
        
        try:
            # 기본적인 일반 멤버 권한만 부여
            basic_permissions = discord.Permissions.none()
            basic_permissions.update(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                connect=True,
                speak=True,
                use_voice_activation=True,
                add_reactions=True,
                use_external_emojis=True,
                change_nickname=True
            )
            
            await verified_role.edit(permissions=basic_permissions)
            await ctx.send(f"✅ '{VERIFIED_ROLE_NAME}' 역할의 권한이 일반 멤버 수준으로 초기화되었습니다.")
            
        except Exception as e:
            await ctx.send(f"권한 초기화 실패: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ImprovedOnboardingManager(bot))