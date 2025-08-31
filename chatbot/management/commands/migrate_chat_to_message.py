"""
管理命令：将旧的 Chat 模型数据迁移到新的 Message 模型
运行命令：python manage.py migrate_chat_to_message
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from chatbot.models import Chat, Message, UserSetting
import uuid


class Command(BaseCommand):
    help = '将旧的 Chat 模型数据迁移到新的 Message 模型'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅预览迁移结果，不实际迁移数据',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('执行干运行模式，不会实际修改数据')
            )

        # 获取所有需要迁移的 Chat 记录
        chats = Chat.objects.all().order_by('user', 'created_at')
        total_chats = chats.count()
        
        if total_chats == 0:
            self.stdout.write(
                self.style.WARNING('没有找到需要迁移的 Chat 记录')
            )
            return

        self.stdout.write(f'找到 {total_chats} 条 Chat 记录需要迁移')

        migrated_count = 0
        user_conversations = {}

        with transaction.atomic():
            for chat in chats:
                # 为每个用户创建一个会话 ID（如果还没有）
                if chat.user.id not in user_conversations:
                    user_conversations[chat.user.id] = uuid.uuid4()
                
                conversation_id = user_conversations[chat.user.id]

                # 检查是否已经存在相应的 Message 记录
                existing_user_msg = Message.objects.filter(
                    user=chat.user,
                    role='user',
                    content=chat.message,
                    created_at=chat.created_at
                ).first()

                existing_assistant_msg = Message.objects.filter(
                    user=chat.user,
                    role='assistant',
                    content=chat.response,
                    created_at=chat.created_at
                ).first()

                if existing_user_msg and existing_assistant_msg:
                    self.stdout.write(
                        self.style.WARNING(
                            f'跳过已存在的记录：用户 {chat.user.username} 在 {chat.created_at}'
                        )
                    )
                    continue

                if not dry_run:
                    # 确保用户有系统提示消息
                    user_setting, _ = UserSetting.objects.get_or_create(user=chat.user)
                    system_msg = Message.objects.filter(
                        user=chat.user,
                        role='system',
                        conversation_id=conversation_id
                    ).first()
                    
                    if not system_msg:
                        Message.objects.create(
                            user=chat.user,
                            role='system',
                            content=user_setting.prompt,
                            conversation_id=conversation_id,
                            created_at=chat.created_at
                        )

                    # 创建用户消息
                    if not existing_user_msg:
                        Message.objects.create(
                            user=chat.user,
                            role='user',
                            content=chat.message,
                            conversation_id=conversation_id,
                            created_at=chat.created_at
                        )

                    # 创建助手回复
                    if not existing_assistant_msg:
                        Message.objects.create(
                            user=chat.user,
                            role='assistant',
                            content=chat.response,
                            conversation_id=conversation_id,
                            created_at=chat.created_at
                        )

                migrated_count += 1
                
                if migrated_count % 10 == 0:
                    self.stdout.write(f'已处理 {migrated_count}/{total_chats} 条记录')

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'干运行完成：共 {migrated_count} 条记录将被迁移'
                    )
                )
                transaction.set_rollback(True)
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'迁移完成：成功迁移 {migrated_count} 条 Chat 记录到 Message 表'
                    )
                )
                
                # 可选：询问是否删除旧的 Chat 记录
                if migrated_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            '\n注意：迁移完成后，您可以考虑删除旧的 Chat 表数据'
                        )
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            '如需删除，请运行：python manage.py migrate_chat_to_message --delete-old'
                        )
                    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅预览迁移结果，不实际迁移数据',
        )
        parser.add_argument(
            '--delete-old',
            action='store_true',
            help='迁移完成后删除旧的 Chat 记录',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_old = options['delete_old']
        
        if delete_old:
            self.delete_old_chats()
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING('执行干运行模式，不会实际修改数据')
            )

        # 获取所有需要迁移的 Chat 记录
        chats = Chat.objects.all().order_by('user', 'created_at')
        total_chats = chats.count()
        
        if total_chats == 0:
            self.stdout.write(
                self.style.WARNING('没有找到需要迁移的 Chat 记录')
            )
            return

        self.stdout.write(f'找到 {total_chats} 条 Chat 记录需要迁移')

        migrated_count = 0
        user_conversations = {}

        with transaction.atomic():
            for chat in chats:
                # 为每个用户创建一个会话 ID（如果还没有）
                if chat.user.id not in user_conversations:
                    user_conversations[chat.user.id] = uuid.uuid4()
                
                conversation_id = user_conversations[chat.user.id]

                # 检查是否已经存在相应的 Message 记录
                existing_user_msg = Message.objects.filter(
                    user=chat.user,
                    role='user',
                    content=chat.message,
                    created_at=chat.created_at
                ).first()

                existing_assistant_msg = Message.objects.filter(
                    user=chat.user,
                    role='assistant',
                    content=chat.response,
                    created_at=chat.created_at
                ).first()

                if existing_user_msg and existing_assistant_msg:
                    self.stdout.write(
                        self.style.WARNING(
                            f'跳过已存在的记录：用户 {chat.user.username} 在 {chat.created_at}'
                        )
                    )
                    continue

                if not dry_run:
                    # 确保用户有系统提示消息
                    user_setting, _ = UserSetting.objects.get_or_create(user=chat.user)
                    system_msg = Message.objects.filter(
                        user=chat.user,
                        role='system',
                        conversation_id=conversation_id
                    ).first()
                    
                    if not system_msg:
                        Message.objects.create(
                            user=chat.user,
                            role='system',
                            content=user_setting.prompt,
                            conversation_id=conversation_id,
                            created_at=chat.created_at
                        )

                    # 创建用户消息
                    if not existing_user_msg:
                        Message.objects.create(
                            user=chat.user,
                            role='user',
                            content=chat.message,
                            conversation_id=conversation_id,
                            created_at=chat.created_at
                        )

                    # 创建助手回复
                    if not existing_assistant_msg:
                        Message.objects.create(
                            user=chat.user,
                            role='assistant',
                            content=chat.response,
                            conversation_id=conversation_id,
                            created_at=chat.created_at
                        )

                migrated_count += 1
                
                if migrated_count % 10 == 0:
                    self.stdout.write(f'已处理 {migrated_count}/{total_chats} 条记录')

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'干运行完成：共 {migrated_count} 条记录将被迁移'
                    )
                )
                transaction.set_rollback(True)
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'迁移完成：成功迁移 {migrated_count} 条 Chat 记录到 Message 表'
                    )
                )
                
                # 可选：询问是否删除旧的 Chat 记录
                if migrated_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            '\n注意：迁移完成后，您可以考虑删除旧的 Chat 表数据'
                        )
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            '如需删除，请运行：python manage.py migrate_chat_to_message --delete-old'
                        )
                    )

    def delete_old_chats(self):
        """删除旧的 Chat 记录"""
        chat_count = Chat.objects.count()
        if chat_count == 0:
            self.stdout.write(
                self.style.WARNING('没有找到需要删除的 Chat 记录')
            )
            return

        confirm = input(f'确认删除 {chat_count} 条旧的 Chat 记录？(y/N): ')
        if confirm.lower() == 'y':
            with transaction.atomic():
                Chat.objects.all().delete()
                self.stdout.write(
                    self.style.SUCCESS(f'已删除 {chat_count} 条旧的 Chat 记录')
                )
        else:
            self.stdout.write('操作已取消')
