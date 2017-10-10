#!/usr/bin/env python3
import sys
import json
import time
import requests
from plumbum import cli

API_URL = 'https://api.vk.com/method/'
TOKEN = '5dfd6b0dee902310df772082421968f4c06443abecbc082a8440cb18910a56daca73ac8d04b25154a1128'
MAX_FRIEND_IN_GROUP = 3


class DeletedUser(Exception):
    pass


class AccesDenied(Exception):
    pass


class UnknownError(Exception):
    pass


class VkApp(cli.Application):
    """Show unique VK groups for specific user"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_called = 0

    def call_method(self, api_method, params={}, frequency=2.9):
        elapsed = time.time() - self.last_called
        left_to_wait = 1.0/frequency - elapsed
        if left_to_wait > 0:
            time.sleep(left_to_wait)
        self.last_called = time.time()
        params['access_token'] = TOKEN
        ready = False
        while not ready:
            r = requests.get(API_URL + api_method, params=params).json()
            sys.stdout.write('.')
            sys.stdout.flush()
            if 'error' in r:
                if r['error']['error_code'] == 18:
                    raise DeletedUser()
                elif r['error']['error_code'] == 15:
                    raise AccesDenied()
                elif r['error']['error_code'] == 10:
                    raise UnknownError()
                elif r['error']['error_code'] == 6:
                    time.sleep(0.5)
                    continue
                else:
                    print(r)
                    raise Exception
            else:
                ready = True
        try:
            res = r['response']
        except KeyError:
            print(r)
            raise
        return res

    def get_friends(self, user_id):
        try:
            res = self.call_method('friends.get', params={'user_id': user_id})
        except (DeletedUser, UnknownError):
            res = []
        return res

    def get_groups(self, user_id):
        try:
            res = self.call_method('groups.get', params={'user_id': user_id})
        except (DeletedUser, UnknownError):
            res = []
        return res

    def is_member(self, group_id, user_id):
        res = self.call_method('groups.isMember', params={'user_id': user_id,
                                                          'group_id': group_id})
        return True if res == 1 else False

    def get_members(self, group_id):
        res = []
        offset = 0
        members_count = self.get_members_count(group_id=group_id)
        while offset < members_count:
            r = self.call_method('groups.getMembers', params={'group_id': group_id,
                                                              'offset': offset})
            res += r['users']
            offset += 1000
        return res

    def get_members_count(self, group_id):
        try:
            r = self.call_method('groups.getMembers', params={'group_id': group_id})
            res = r['count']
        except (AccesDenied, UnknownError):
            res = 0
        return res

    def get_group_info(self, group_id):
        try:
            r = self.call_method('groups.getById', params={'group_id': group_id})
            res = r[0]
        except (AccesDenied, UnknownError):
            res = {}
        return res

    @cli.switch(['--id'], int, mandatory=True)
    def set_user_id(self, user_id):
        self.user_id = user_id

    def main(self):
        unique_group_ids = []
        user_groups = self.get_groups(user_id=self.user_id)
        user_friends = set(self.get_friends(user_id=self.user_id))
        for user_group_id in user_groups:
            members = set(self.get_members(group_id=user_group_id))
            friends_in_group = members & user_friends
            if len(friends_in_group) <= MAX_FRIEND_IN_GROUP:
                unique_group_ids.append(user_group_id)

        unique_groups = []
        for group_id in unique_group_ids:
            group_info = self.get_group_info(group_id=group_id)
            if group_info:
                unique_groups.append({'name': group_info['name'],
                                      'gid': group_id,
                                      'members_count': self.get_members_count(group_id=group_id)})
        json.dump(unique_groups, open('groups.json', 'w'))


if __name__ == '__main__':
    VkApp.run()
