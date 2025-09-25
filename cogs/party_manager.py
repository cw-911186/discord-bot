import discord
from discord.ext import commands
from discord import ui, app_commands
import asyncio

# --- 파티 카드 View (참가자/관전자 버튼) ---
class PartyCardView(ui.View):
    def __init__(self, bot, party_vc_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.party_vc_id = party_vc_id

    def has_verified_role(self, member: discord.Member) -> bool:
        """멤버가 인증완료 역할을 가지고 있는지 확인"""
        VERIFIED_ROLE_NAME = "인증완료"
        return any(role.name == VERIFIED_ROLE_NAME for role in member.roles)

    async def update_embed(self, interaction: discord.Interaction):
        """파티 카드 임베드를 최신 정보로 업데이트하는 함수"""
        cog = self.bot.get_cog('PartyManager')
        if not cog: return

        party_info = cog.active_parties.get(self.party_vc_id)
        if not party_info:
            await interaction.message.delete()
            self.stop()
            return

        # 참가자/관전자 목록을 짧은 이름으로 변환
        guild = interaction.guild
        participants_names = []
        for uid in party_info['participants']:
            member = guild.get_member(uid)
            participants_names.append(cog.get_short_name(member.display_name) if member else f"나간 유저({uid})")

        spectators_names = []
        for uid in party_info['spectators']:
            member = guild.get_member(uid)
            spectators_names.append(cog.get_short_name(member.display_name) if member else f"나간 유저({uid})")

        embed = interaction.message.embeds[0]
        embed.set_field_at(2, name="👥 참가자 목록", value='\n'.join(participants_names) if participants_names else "없음", inline=True)
        embed.set_field_at(3, name="👀 관전자 목록", value='\n'.join(spectators_names) if spectators_names else "없음", inline=True)
        embed.set_field_at(1, name="📊 현재 인원", value=f"{len(party_info['participants'])} / {party_info['max_size']}", inline=False)
        
        await interaction.message.edit(embed=embed)

    async def handle_join(self, interaction: discord.Interaction, join_type: str):
        user = interaction.user
        
        # 인증완료 역할 확인
        if not self.has_verified_role(user):
            await interaction.response.send_message(
                "❌ **파티 참여 권한이 없습니다.**\n\n"
                "파티에 참여하려면 먼저 온보딩 과정을 완료해야 합니다.\n"
                "📍 #입장-온보딩 채널에서 닉네임 설정과 역할 선택을 완료해주세요.", 
                ephemeral=True
            )
            return
        
        if not user.voice or user.voice.channel.id != self.party_vc_id:
            await interaction.response.send_message("❗ 먼저 파티 음성 채널에 참여해야 합니다.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        cog = self.bot.get_cog('PartyManager')
        if not cog: return

        party_info = cog.active_parties.get(self.party_vc_id)
        if not party_info: return

        # 참가자 버튼을 누른 경우
        if join_type == 'participant':
            if user.id in party_info['participants']:
                await interaction.followup.send("이미 참가자로 등록되어 있습니다.", ephemeral=True)
                return
            
            if user.id in party_info['spectators']:
                party_info['spectators'].remove(user.id)
            
            if len(party_info['participants']) >= party_info['max_size']:
                party_info['spectators'].add(user.id)
                await interaction.followup.send("파티 인원이 가득 차서 관전자로 배정되었습니다.", ephemeral=True)
            else:
                party_info['participants'].add(user.id)
                await interaction.followup.send("참가자로 배정되었습니다.", ephemeral=True)
        
        elif join_type == 'spectator':
            if user.id in party_info['spectators']:
                await interaction.followup.send("이미 관전자로 등록되어 있습니다.", ephemeral=True)
                return
            
            if user.id in party_info['participants']:
                party_info['participants'].remove(user.id)
            
            party_info['spectators'].add(user.id)
            await interaction.followup.send("관전자로 배정되었습니다.", ephemeral=True)
        
        await self.update_embed(interaction)

    @ui.button(label="참가자", style=discord.ButtonStyle.success, custom_id="party_join_participant")
    async def join_participant(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_join(interaction, 'participant')

    @ui.button(label="관전자", style=discord.ButtonStyle.secondary, custom_id="party_join_spectator")
    async def join_spectator(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_join(interaction, 'spectator')


# --- 파티 설정 View (드롭다운, 생성 버튼) ---
class PartySetupView(ui.View):
    def __init__(self, bot, author, thread):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.thread = thread
        self.selected_mode