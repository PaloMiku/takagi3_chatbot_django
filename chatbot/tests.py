from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import UserSetting, Message, Chat


class ChatBasicTest(TestCase):
	def setUp(self):
		self.client = Client()
		self.user = User.objects.create_user(username='u1', password='pass12345')
		UserSetting.objects.create(user=self.user)

	def test_post_message_creates_chat_and_message(self):
		self.client.login(username='u1', password='pass12345')
		resp = self.client.post(reverse('chatbot'), {'message': '你好'})
		self.assertEqual(resp.status_code, 200)
		self.assertTrue(Chat.objects.filter(user=self.user, message='你好').exists())
		self.assertTrue(Message.objects.filter(user=self.user, role='user', content='你好').exists())
