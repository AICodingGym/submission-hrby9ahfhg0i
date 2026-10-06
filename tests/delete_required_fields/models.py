from django.db import models


class Avatar(models.Model):
    desc = models.TextField(null=True)


class User(models.Model):
    avatar = models.ForeignKey(Avatar, models.CASCADE, null=True)


class Parent(models.Model):
    pass


class Child(Parent):
    pass


class RequiredFieldsChild(models.Model):
    avatar = models.ForeignKey(Avatar, models.CASCADE)
    code = models.CharField(max_length=30, unique=True)
    payload = models.TextField()


class RequiredFieldsLeaf(models.Model):
    child = models.ForeignKey(RequiredFieldsChild, models.CASCADE, to_field='code')


class RequiredFieldsInheritedChild(Avatar):
    parent = models.ForeignKey(Parent, models.CASCADE)
