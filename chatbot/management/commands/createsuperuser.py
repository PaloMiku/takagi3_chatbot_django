import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from django.core import exceptions


class Command(BaseCommand):
    help = "创建超级用户（无 'leave blank to use ...' 提示，强制手动输入用户名/邮箱/密码）。"

    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--username', dest='username', help='指定用户名')
        parser.add_argument('--email', dest='email', help='指定邮箱')
        parser.add_argument('--noinput', action='store_true', help='非交互模式，从环境变量读取')

    def handle(self, *args, **options):
        UserModel = get_user_model()
        username_field = UserModel.USERNAME_FIELD
        database = 'default'

        if options.get('noinput'):
            username = options.get('username') or self.getenv(f'DJANGO_SUPERUSER_{username_field.upper()}')
            email = options.get('email') or self.getenv('DJANGO_SUPERUSER_EMAIL')
            password = self.getenv('DJANGO_SUPERUSER_PASSWORD')
            if not username or not password:
                raise CommandError('noinput 模式需要设置用户名与密码环境变量')
            data = {username_field: username, 'email': email}
            self._create(UserModel, data, password, database)
            self.stdout.write(self.style.SUCCESS(f"超级用户 '{username}' 已创建"))
            return

        # 交互模式
        username = options.get('username')
        while not username:
            username = input('用户名: ').strip()
            if not username:
                self.stderr.write(self.style.ERROR('用户名不能为空'))

        email_field = None
        if any(f.name == 'email' for f in UserModel._meta.get_fields()):
            email_field = 'email'
        email = options.get('email')
        if email_field:
            while not email:
                email = input('邮箱: ').strip()
                if not email:
                    self.stderr.write(self.style.ERROR('邮箱不能为空'))

        # 密码双输入确认
        password = None
        while True:
            pwd1 = getpass.getpass('密码: ')
            if not pwd1:
                self.stderr.write(self.style.ERROR('密码不能为空'))
                continue
            pwd2 = getpass.getpass('再次输入密码: ')
            if pwd1 != pwd2:
                self.stderr.write(self.style.ERROR('两次输入不一致'))
                continue
            # 校验密码策略
            fake_user = UserModel(**{username_field: username, 'email': email})
            try:
                validate_password(pwd1, user=fake_user)
            except exceptions.ValidationError as e:
                for msg in e.messages:
                    self.stderr.write(self.style.ERROR(msg))
                continue
            password = pwd1
            break

        data = {username_field: username}
        if email_field:
            data['email'] = email
        self._create(UserModel, data, password, database)
        self.stdout.write(self.style.SUCCESS(f"超级用户 '{username}' 已创建"))

    def _create(self, UserModel, data, password, database):
        try:
            user = UserModel._default_manager.db_manager(database).create_superuser(**data)
        except IntegrityError:
            raise CommandError('用户已存在')
        user.set_password(password)
        user.save()

    @staticmethod
    def getenv(name):
        import os
        return os.getenv(name)
