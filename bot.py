#!/usr/bin/python3.5
import discord
import asyncio
import json
import pickle
import time
import datetime
import dateutil.relativedelta
import enum
import random

# Hi fellow source code readers!

### Major Todo Stuff ###
# figure out how coroutines actually work and make a properly working ConsoleInterface
# ...as well as potentially adding interfaces to other chat services (chatango, skype, tinychat... irc... minecraft!)
# add a locale / language system, and cleanup all the _super messy_ language manipulation code

### Misc Todo Stuff ###
# non fridge related roleplaying and utility commands
# music generation command involving parsing solfege and playing through voice channels
# a custom configuration file format would be nicer than the messy json currently used

### Future Considerations Stuff ###
# donate command (from one minifridge to another <3)
# admin commmands for easily navigating and manipulating the entire Fridgeverse tree
# user statistic commands, for roleplaying pursposes

### Content Ideas and Stuff ###
# ovens that cook (meaning adding ticks Fridgeverse)
# tator tots and other food items to be cooked and eaten (meaning adding self deletion)
# living creatures and pets! (meaning make use of ongioing interactions)
# keys and combination locks (meaning commands that involve multiple items from the fridge)
# alchemy things
# messaging things, phones, bullitin boards... remote detonators...
# augmented reality stuff?

### Configuration Stuff ###

bot_trigger = "!"
token_file = "token"
permissions_file = "permissions.cfg"
save_file = "fridgeverse.sav"
log_file = "fridge.log"
logging = True
max_message_length = 2000

### Utility Stuff ###

def to_int(string):
	try:
		return int(string)
	except:
		return None

### Permissions Stuff

class CommandClass(enum.Enum):
	common = 1
	fridge = 2
	admin = 3

def command_class_from_string(string):
	if string == "common":
		return CommandClass.common
	elif string == "fridge":
		return CommandClass.fridge
	elif string == "admin":
		return CommandClass.admin
	else:
		return None

# a dictionary of special permissions per user
# a tuple where the first item is gained permissions
# and where the second item is lost permissions
permissions = {"Aardbei#8517": ([CommandClass.admin], [])} # default
# permissions that users have by defailt
standard_permissions = [CommandClass.fridge, CommandClass.common]

# get the final effective permissions for a user
def get_permissions(user):
	final = list(standard_permissions)
	if str(user) in permissions.keys():
		for gained in permissions[str(user)][0]:
			final.append(gained)
		for lost in permissions[str(user)][1]:
			final.remove(lost)
	return final

class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, enum.Enum):
            return {"__enum__": str(obj)}
        return json.JSONEncoder.default(self, obj)

def as_enum(d): # Unsafe function. OK here since only used in load_permissions on a trusted config file.
    if "__enum__" in d:
        name, member = d["__enum__"].split(".")
        return getattr(globals()[name], member)
    else:
        return d

def save_permissions(save_file=permissions_file):
	with open(save_file, "w", encoding='UTF-8') as f:
		json.dump(permissions, f, cls=EnumEncoder)

def load_permissions(save_file=permissions_file):
	with open(save_file, "r", encoding='UTF-8') as f:
		return json.load(f, object_hook=as_enum)

def init_permissions():
	global permissions
	import os.path
	if os.path.exists(permissions_file):
		permissions = load_permissions()
	else:
		save_permissions()

### Global Variables and Stuff ###

ignore_messages = []

### Logging Stuff ###

def log(message):
	with open(log_file, "a", encoding='UTF-8') as f:
		entry = "\t".join([str(message.id), str(message.timestamp), str(message.edited_timestamp), str(message.server), str(message.author), message.content])
		f.write(entry + "\n")

### World Stuff ###

class Entity():
	def __init__(self, entity_name, fridge=False, private=False, parent=None, creator=None, description="A very average thing."):
		self.entity_name = entity_name
		self.contents = []
		self.fridge = fridge
		self.private = private
		self.parent = parent
		self.creator = creator
		self.created_time = time.time()
		self.last_user = None
		self.last_used = None
		self.description = description

		self.max_contents = 3
		self.movable = True

	def is_full(self):
		return len(self.contents) >= self.max_contents

	def remaining_space(self):
		return self.max_contents - len(self.contents)

	def can_hold_things(self):
		return self.max_contents > 0

	def get_display_name(self):
		if self.fridge:
			if self.private:
				return self.entity_name + "'s minifridge"
			else:
				return "Fridge of #" + self.entity_name
		else:
			return self.entity_name

	# take an entity from this entity's contents
	def take_from(self, entity):
		if entity in self.contents:
			self.contents.remove(entity)
			entity.parent = None
			return entity
		else:
			return None

	# takes an entity by name from this entity's contents
	def take_from_by_name(self, entity_name):
		entity = self.get_entity(entity_name)
		if entity == None:
			return None
		else:
			self.contents.remove(entity)
			entity.parent = None
			return entity

	# take this entity out of its parent entity
	def take(self):
		if self.parent != None:
			self.parent.contents.remove(self)
			self.parent = None
			return self
		else:
			return None

	# put this entity into another entity
	def put(self, parent):
		self.take()
		parent.contents.append(self)
		self.parent = parent

	# put another entity into this entity
	def put_into(self, entity):
		entity.take()
		self.contents.append(entity)
		entity.parent = self

	# get an entity from contents by name
	def get_entity(self, entity_name):
		for entity in self.contents:
			if entity_name.lower() == entity.entity_name.lower():
				return entity
		return None

	# get an entity and create it if it doesn't exist
	def get_entity_implicit(self, entity_name):
		entity = self.get_entity(entity_name)
		if entity == None:
			entity = Entity(entity_name)
			self.put_into(entity)
		return entity

	# find out how many entities of a given name are contained in this entity
	def count_entity(self, entity_name):
		count = 0
		for entity in self.contents:
			if entity_name.lower() == entity.entity_name.lower():
				count += 1
		return count

	async def interact(self, interface, user, args):
		self.last_user = str(user)
		self.last_used = time.time()
		await self.action(interface, user, args)

	# virtual function
	async def action(self, interface, user, args):
		arg = " ".join(args).lower()
		if arg == "poke":
			await interface.print(user.name + " pokes the " + self.entity_name + ".  Not much happens.")
		elif arg == "punch":
			await interface.print(user.name + " picks a fight with the " + self.entity_name + ".  It takes a beating.  Don't worry, though, it's okay.")
		elif arg == "eat":
			await interface.print(user.name + " stuffs the " + self.entity_name + " in their mouth.")
		else:
			await interface.print("Nothing happened.")

	# give a description of the current state of the thing
	# virtual function
	def check(self, user):
		return "It looks like quite an average thing."

	async def about(self, interface, user, args):
		entity_name = self.get_display_name()
		about_string = "The name of the thing is **" + self.entity_name + "**.\n"
		about_string += "\"_" + self.description + "_\" is what they say about it.\n"
		if self.parent == None:
			about_string += "_The " + self.entity_name + " is floating around Frideverse somewhere unknown._\n"
		else:
			about_string += "The whereabouts of the " + self.entity_name + " are **" + self.parent.get_display_name() + "**.\n"
		if self.creator == None:
			about_string += "_Nobody knows where the " + self.entity_name + " came from._\n"
		else:
			about_string += "**" + self.creator + "** is who made the " + self.entity_name + ".\n"
		now_date = datetime.datetime.now()
		created_date = datetime.datetime.fromtimestamp(self.created_time)
		delta = dateutil.relativedelta.relativedelta(now_date, created_date)
		age_string = "%d years, %d months, %d days, %d hours, %d minutes, and %d seconds" % (delta.years, delta.months, delta.days, delta.hours, delta.minutes, delta.seconds)
		about_string += "The " + self.entity_name + " is **" + age_string + "** old.\n"
		if self.last_user == None:
			about_string += "_The " + self.entity_name + " has never been touched by anyone. </3_"
		else:
			about_string += "The last person to touch the " + self.entity_name + " is **" + self.last_user + "**.\n"
			used_date = datetime.datetime.fromtimestamp(self.last_used)
			delta = dateutil.relativedelta.relativedelta(now_date, used_date)
			used_age = "%d years, %d months, %d days, %d hours, %d minutes, and %d seconds" % (delta.years, delta.months, delta.days, delta.hours, delta.minutes, delta.seconds)
			about_string += "And that was **" + used_age + "** ago."
		await interface.print(about_string)
	
	# text heiarchy
	def to_string(self, pre=""):
		s = pre + self.entity_name + "\n"
		for e in self.contents:
			s += e.to_string(pre + "> ")
		return s

class EntityBag(Entity):
	def __init__(self):
		super().__init__("bag", description="A bag to stuff a handful of things in.")
		self.max_contents = 10
		
	async def action(self, interface, user, args):
		arg = " ".join(args).lower()
		if len(args) == 0:
			await interface.print("The bag doesn't respond.")
		elif arg == "poke":
			await interface.print(user.name + " slightly depresses the fabric of the bag with their poking and prodding.")
		elif arg == "eat":
			if len(self.contents) > 2:
				await interface.print(user.name + " tries to stuff the bag in their mouth, but it's too full to fit.")
			else:
				await interface.print(user.name + " stuffs the bag in their mouth.  It tastes like fabric.")
		elif arg == "punch":
			if len(self.contents) > 0:
				await interface.print(user.name + " uses the bag as a punching bag, disturbing the contents a little.")
			else:
				await interface.print(user.name + " tries to use the bag as a punching bag, but it doesn't resist too well since there's nothing in it.")
		else:
			await interface.print("You can't do that to a bag.")

	def check(self, user):
		return "The bag looks like it can fit " + str(self.remaining_space()) + " more things inside."

class EntityNote(Entity):
	def __init__(self):
		super().__init__("note", description="A scratch peice of paper that can be written on.")
		self.max_contents = 0
		self.message = ""
		
	async def action(self, interface, user, args):
		arg = " ".join(args).lower()
		if len(args) == 0:
			await interface.print("The peice of paper doesn't do much on its own.")
		elif arg == "poke":
			await interface.print("The peice of paper folds inward as " + user.name + " pokes it.")
		elif arg == "eat":
			await interface.print(user.name + " balls the paper up and puts it in their mouth. The moisture smears the surface a bit.")
			letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
			new_message = ""
			for c in self.message:
				if c in letters and random.randint(0, 7) == 0:
					new_message += random.choice(letters)
				else:
					new_message += c
			self.message = new_message
			
		elif arg == "punch":
			await interface.print(user.name + " beats up the note.  Don't worry, it's okay.")
		elif arg == "read":
			await interface.print(self.check(user))
		elif args[0].lower() == "write":
			if len(args) < 2:
				await interface.print("What do you want to write on the paper?")
			else:
				self.message = " ".join(args[1:])
				await interface.print(user.name + " jotted something onto the paper.")
		else:
			await interface.print("You can't do that to a peice of paper.")

	def check(self, user):
		if self.message == "":
			return "The note is empty.  Maybe you can write on it..."
		else:
			return "There is something written on the paper.  It looks like it says, \"_" + self.message + "_\""

def create_thing(thing_name):
	if thing_name.lower() in ["bag"]:
		return EntityBag()
	elif thing_name.lower() in ["note", "paper", "peice of paper"]:
		return EntityNote()
	else:
		return Entity(thing_name)

def get_mini_fridge(user_id):
	entity = mini_fridges.get_entity_implicit(user_id)
	entity.fridge = True
	entity.private = True
	entity.max_contents = 50
	return entity

def get_server_fridge(server):
	return server_fridges.get_entity_implicit(server)

def get_channel_fridge(server, channel):
	entity = get_server_fridge(server).get_entity_implicit(channel)
	entity.fridge = True
	entity.private = False
	entity.max_contents = 200
	return entity

def print_world():
	print(root_entity.to_string())

def save_world(save_file=save_file):
	with open(save_file, "wb") as f:
		pickle.dump(root_entity, f, pickle.HIGHEST_PROTOCOL)

def load_world(save_file=save_file):
	with open(save_file, "rb") as f:
		return pickle.load(f)

def generate_world():
	root_entity = Entity("Fridgeverse")
	mini_fridges =  Entity("Mini Fridges")
	server_fridges = Entity("Server Fridges")
	mini_fridges.put(root_entity)
	server_fridges.put(root_entity)
	return root_entity

def init_world():
	global root_entity
	global mini_fridges
	global server_fridges
	import os.path
	if os.path.exists(save_file):
		root_entity = load_world()
	else:
		root_entity = generate_world()
	mini_fridges = root_entity.get_entity("Mini Fridges")
	server_fridges = root_entity.get_entity("Server Fridges")

### Commands Stuff ###

class Command():
	def __init__(self, aliases, description="A generic command", command_class=CommandClass.common, help="There's no help for this command.", usage="", minimum_arguments=0):
		self.aliases = aliases
		self.description = description
		self.command_class = command_class
		self.help = help
		self.usage = usage
		self.minimum_arguments = minimum_arguments

	def can_invoke(self, interface):
		return self.command_class in interface.get_permissions()

	async def invoke(self, interface, user, args=[]):
		if not self.can_invoke(interface):
			await interface.print("You aren't allowed to use that command!")
		elif len(args) < self.minimum_arguments:
			await self.print_usage(interface)
		else:
			await self.action(interface, user, args)

	def get_description_string(self):
		aliases = [bot_trigger + alias for alias in self.aliases]
		aliases[0] = "**" + aliases[0] + "**"
		return "(_" + self.command_class.name + "_ command) " + ", ".join(aliases) + " - **" + self.description + "**"

	def get_usage_string(self):
		return "_Usage: " + bot_trigger + self.aliases[0] + " " + self.usage + "_"

	async def print_usage(self, interface):
		await interface.print(self.get_usage_string())

	async def print_help(self, interface):
		description_string = self.get_description_string()
		usage_string = self.get_usage_string()
		help_string = description_string + "\n" + usage_string + "\n\n" + self.help
		await interface.print(help_string)

	# virtual method
	async def action(self, interface, user, args=[]):
		pass

class TestCommand(Command):
	def __init__(self):
		super().__init__(["test", "test2"], "this is a test command", CommandClass.admin, "this is the supposed extended help ttext weeeeee", "[something]", 1)

	async def action(self, interface, user, args=[]):
		await interface.print("oops, yeah i'm a test, hi, and that arg was " + args[0])

class StoryTestCommand(Command):
	def __init__(self):
		super().__init__(["storytest"], "this is a test command for testing interactions", CommandClass.admin)

	async def action(self, interface, user, args=[]):
		await interface.print("yo yo yo, tell me a **fruit**")
		response = await interface.read()
		await interface.print("yeah yo, " + response + " is a _fantastic_ fruit")

class ChannelIdCommand(Command):
	def __init__(self):
		super().__init__(["channelid"], "Print the ID of the channel.", CommandClass.admin)

	async def action(self, interface, user, args=[]):
		await interface.print("Channel ID: **" + interface.channel.id + "**")

class UserIdCommand(Command):
	def __init__(self):
		super().__init__(["userid"], "Print the ID of your user.", CommandClass.admin)

	async def action(self, interface, user, args=[]):
		await interface.print("User ID: **" + user.id + "**")

class WorldCommand(Command):
	def __init__(self):
		super().__init__(["world"], "Print an outline of all things in Fridgeverse.", CommandClass.admin)

	async def action(self, interface, user, args=[]):
		await interface.print(root_entity.to_string())

class CommandsCommand(Command):
	def __init__(self):
		super().__init__(["commands"], "List all recognized commands.", CommandClass.common, "The commands command prints a listing of all of the commands that Fridge Bot knows.  They are sorted first by _command class_ and then by _default alias_.  Listed for each command are its _command class_, a list of its _aliases_, and its _short description_.  Bolded for convenience are its _default alias_ and its _short description_.\n\nIf you invoke this command without any arguments, it will only list commands that you are allowed to invoke according to command class.  If you pass \"all\" as an argument, all of the commands will be listed, whether you can invoke them yourself or not.", "{\"all\"}")

	async def action(self, interface, user, args=[]):
		command_list = get_unique_commands()
		if len(args) == 0 or args[0].lower() != "all":
			command_list = [i for i in command_list if i.can_invoke(interface)]
		lines = []
		command_list.sort(key=lambda x: (x.command_class.value, x.aliases[0]))
		for command in command_list:
			lines.append(command.get_description_string())
		await interface.print("\n".join(lines))

class HelpCommand(Command):
	def __init__(self):
		super().__init__(["help", "usage", "description"], "Explain a command in detail.", CommandClass.common, "The help command will print extended information about a given command, including the _command class_, the list of all the _aliases_ that can be used to invoke the command, the _short description_, a descrption of its _usage syntax_ including optional and required _parameters_, and a _detailed description_ of what the command does. (Like this one!)\n\nThe _command class_ indicates who is able to invoke the command.  Every user has their own _permissions_ set of command classes that they are allowed to use.\n\nMany commands have more than one _alias_ by which you can invoke it.  The default alias is bolded in the command description and used to describe its usage syntax.\n\nThe _short description_ provides an brief overview of what the command does.\n\nThe _usage syntax_ describes how to use the command.  Required parameters are indicated with [square brackets] and optional parameters are indicated with {curly brackets}.  \"Quotation marks\" denote that the parameter is a specific word rather than a variable value.  A set of accepted values is denoted by a series delimited by | pipe | characters.\n\nFinally, the _detailed description_ goes into further detail about every aspect of the command. (Like this one!)", "[command]")

	async def action(self, interface, user, args=[]):
		if len(args) == 0:
			await invoke_command(interface, user, "help", ["help"])
		else:
			command = args[0].lower()
			if command in commands.keys():
				await commands[command].print_help(interface)
			else:
				await interface.print("Fridge Bot doesn't know about _" + args[0] + "_.")

class LookCommand(Command):
	def __init__(self):
		super().__init__(["look", "see", "view", "contents", "fridge", "list", "dir", "ls", "open"], "See the contents of the fridge.", CommandClass.fridge, "The look command lists off all of the things in the fridge of the channel used to invoke the command.  If you invoke the command by direct message, you will see the contents of your _personal minifridge_.  If you invoke the command in a channel of a server, you will see the contents of the _channel fridge_ that is shared by every member of the channel.")

	async def action(self, interface, user, args=[]):
		if interface.channel.is_private:
			fridge_name = "your minifridge"
		else:
			fridge_name = "the fridge"
		entity_counts = {}
		for entity in interface.get_fridge().contents:
			entity_name = entity.entity_name
			if entity_name in entity_counts.keys():
				entity_counts[entity_name] += 1
			else:
				entity_counts[entity_name] = 1
		entity_names = []
		entity_keys = list(entity_counts.keys())
		entity_keys.sort()
		for entity_name in entity_keys:
			entity_count = entity_counts[entity_name]
			if entity_count == 1:
				if entity_name[0] in ["a", "e", "i", "o", "u"]:
					entity_name = "an " + entity_name
				else:
					entity_name = "a " + entity_name
			elif entity_count > 1:
				entity_name = str(entity_count) + " " + entity_name
				if entity_name[-1] in ["s", "x"]:
					entity_name += "es"
				elif entity_name[-1] == "y":
					entity_name = entity_name[:-1] + "ies"
				else:
					entity_name += "s"
			entity_name = "**" + entity_name + "**"
			entity_names.append(entity_name)
		if len(entity_names) > 2:
			message = "Inside " + fridge_name + " are " + ", ".join(entity_names[:-1]) + ", and " + entity_names[-1] + "."
		elif len(entity_names) > 1:
			message = "Inside " + fridge_name + " are " + entity_names[0] + " and " + entity_names[1] + "."
		elif len(entity_names) > 0:
			if list(entity_counts.values())[0] > 1:
				message = "Inside " + fridge_name + " are " + entity_names[0] + "."
			else:
				message = "Inside " + fridge_name + " is " + entity_names[0] + "."
		else:
			message = "Nothing is inside " + fridge_name + "!"
		await interface.print(message)

class StoreCommand(Command):
	def __init__(self):
		super().__init__(["put", "store", "insert", "drop"], "Take something out of your minifridge and put it in the channel fridge.", CommandClass.fridge, "The put command moves a thing from your minifridge to the fridge of the channel used to invoke the command.  Since the fridge of a direct message channel is your _personal minifridge_, there will be no effect if you invoke this command by direct message because it will take the thing from your minifridge and put it back in your minifridge.  This command has the reverse effect of the _take_ command.  You can optionally pass a number as the first argument to store an amount other than 1 if you have that amount.", "{amount} [thing name]", 1)

	async def action(self, interface, user, args=[]):
		if to_int(args[0]) != None:
			amount = to_int(args.pop(0))
		else:
			amount = 1
		entity_name = " ".join(args)
		if amount <= 0:
			await interface.print("Nothing happened.")
		else:
			if amount != 1:
				if entity_name.endswith("ies"):
					entity_name = entity_name[:-3] + "y"
				elif entity_name.endswith("les"):
					entity_name = entity_name[:-1]
				elif entity_name.endswith("es"):
					entity_name = entity_name[:-2]
				elif entity_name.endswith("s"):
					entity_name = entity_name[:-1]
			count = get_mini_fridge(str(user)).count_entity(entity_name)
			if count == 0:
				await interface.print("No such _" + entity_name + "_ is in " + user.name + "'s minifridge!")
			elif amount > count:
				await interface.print("There are only **" + str(count) + "** of **" + entity_name + "** in " + user.name + "'s minifridge!")
			elif interface.get_fridge().is_full():
				await interface.print("The fridge is full and won't handle anymore things stuffed into it!")
			elif interface.get_fridge().remaining_space() < amount:
				await interface.print("The fridge is too full to handle that many more things stuffed inside of it!")
			else:
				for i in range(amount):
					entity = get_mini_fridge(str(user)).get_entity(entity_name)
					if not entity.movable:
						await interface.print("The " + entity_name + " is glued inside of the fridge and won't move.")
						return
					entity.put(interface.get_fridge())
				if amount == 1:
					determiner_word = "The"
				else:
					determiner_word = str(amount) + " of"
				await interface.print(determiner_word + " " + entity_name + " was taken from " + user.name + "'s minifridge and put in the fridge.")
				await invoke_command(interface, user, "look")
				save_world()

class TakeCommand(Command):
	def __init__(self):
		super().__init__(["take", "remove", "get", "grab", "pickup"], "Take something from the fridge and put it in your own minifridge.", CommandClass.fridge, "The take command moves a thing from the fridge of the channel used to invoke the command to your minifridge.  Since the fridge of a direct message channel is your _personal minifridge_, there will be no effect if you invoke this command by direct message because it will take the thing from your minifridge and put it back in your minifridge.  This command has the reverse effect of the _store_ command.  You can optionally pass a number as the first argument to take an amount other than 1 if that amount is there.", "{amount} [thing name]", 1)

	async def action(self, interface, user, args=[]):
		if to_int(args[0]) != None:
			amount = to_int(args.pop(0))
		else:
			amount = 1
		entity_name = " ".join(args)
		if amount <= 0:
			await interface.print("Nothing happened.")
		else:
			if amount != 1:
				if entity_name.endswith("ies"):
					entity_name = entity_name[:-3] + "y"
				elif entity_name.endswith("les"):
					entity_name = entity_name[:-1]
				elif entity_name.endswith("es"):
					entity_name = entity_name[:-2]
				elif entity_name.endswith("s"):
					entity_name = entity_name[:-1]
			count = interface.get_fridge().count_entity(entity_name)
			if count == 0:
				await interface.print("No such _" + entity_name + "_ is in the fridge!")
			elif amount > count:
				await interface.print("There are only **" + str(count) + "** of **" + entity_name + "** in the fridge!")
			elif get_mini_fridge(str(user)).is_full():
				await interface.print(user.name + "'s minifridge is full and won't handle anymore things stuffed into it!")
			elif get_mini_fridge(str(user)).remaining_space() < amount:
				await interface.print(user.name + "'s minifridge is too full to handle that many more things stuffed inside of it!")
			else:
				for i in range(amount):
					entity = interface.get_fridge().get_entity(entity_name)
					if not entity.movable:
						await interface.print("The " + entity_name + " is glued inside of the fridge and won't move.")
						return
					entity.put(get_mini_fridge(str(user)))
				if amount == 1:
					determiner_word = "The"
				else:
					determiner_word = str(amount) + " of"
				await interface.print(determiner_word + " " + entity_name + " was taken from the fridge and put in " + user.name + "'s minifridge.")
				await invoke_command(interface, user, "look")
				save_world()

class DespawnCommand(Command):
	def __init__(self):
		super().__init__(["despawn", "destroy", "degenerate", "delete"], "Despawn a thing from the fridge.", CommandClass.admin, "The despawn command disintegrates a thing taken from the fridge of the channel used to invoke the command from all of Fridgeverse leaving no records of its former existence.", "[thing name]", 1)

	async def action(self, interface, user, args=[]):
		if to_int(args[0]) != None:
			amount = to_int(args.pop(0))
		else:
			amount = 1
		entity_name = " ".join(args)
		if amount <= 0:
			await interface.print("Nothing happened.")
		else:
			if amount != 1:
				if entity_name.endswith("ies"):
					entity_name = entity_name[:-3] + "y"
				elif entity_name.endswith("les"):
					entity_name = entity_name[:-1]
				elif entity_name.endswith("es"):
					entity_name = entity_name[:-2]
				elif entity_name.endswith("s"):
					entity_name = entity_name[:-1]
			count = interface.get_fridge().count_entity(entity_name)
			if count == 0:
				await interface.print("No such _" + entity_name + "_ is in the fridge!")
			elif amount > count:
				await interface.print("There are only **" + str(count) + "** of **" + entity_name + "** in the fridge!")
			else:
				for i in range(amount):
					interface.get_fridge().get_entity(entity_name).take()
				await invoke_command(interface, user, "look")
				save_world()

class SpawnCommand(Command):
	def __init__(self):
		super().__init__(["spawn", "create", "generate", "add", "make"], "Spawn a new thing in the fridge.", CommandClass.admin, "The spawn command materializes a new thing and puts it in the fridge of the channel used to invoke the command.  The newly created thing is timestamped and marked with the name of the creator upon creation so that its age and creator can always be known by the _info_ command.\n\nIf the name of the thing to be created is a recognized _special type of thing_, then the thing will take on the _special properties and functionality_ of such special type of thing.  Otherwise it will take on _generic properties and functionality_.", "{amount} [thing name]", 1)

	async def action(self, interface, user, args=[]):
		if to_int(args[0]) != None:
			amount = to_int(args.pop(0))
		else:
			amount = 1
		entity_name = " ".join(args)
		if amount <= 0:
			await interface.print("Nothing happened.")
		else:
			if amount != 1:
				if entity_name.endswith("ies"):
					entity_name = entity_name[:-3] + "y"
				elif entity_name.endswith("les"):
					entity_name = entity_name[:-1]
				elif entity_name.endswith("es"):
					entity_name = entity_name[:-2]
				elif entity_name.endswith("s"):
					entity_name = entity_name[:-1]
			if interface.get_fridge().is_full():
				await interface.print("The fridge is full and won't handle anymore things stuffed into it!")
			elif interface.get_fridge().remaining_space() < amount:
				await interface.print("The fridge is too full to handle that many more things stuffed inside of it!")
			else:
				for i in range(amount):
					entity = create_thing(entity_name)
					entity.creator = str(user)
					entity.put(interface.get_fridge())
				await invoke_command(interface, user, "look")
				save_world()

class InteractCommand(Command):
	def __init__(self):
		super().__init__(["use", "interact", "engage", "action"], "Interact with a thing in the fridge.", CommandClass.fridge, "The use command triggers the _special functionality_ of a thing from the fridge of the channel used to invoke the command.  Only _special types of things_ possess _special properties and functionality_.  If you invoke this command on a _generic type of thing_, nothing will happen.\n\nUpon interacting with a thing, the thing is timestamped and marked with the name of the user interacting with it so that its activity can always be known by the _info_ command.\n\nIf you pass arguments to this command, they must follow an initial comma separating the name of the thing and the list of arguments.", "[thing name] {, list of arguments}", 1)

	async def action(self, interface, user, args=[]):
		entity_name = " ".join(args)
		if "," in entity_name:
			entity_name, arg = entity_name.split(",", 1)
			entity_name = entity_name.strip()
			arg = arg.strip().split()
		else:
			arg = []
		entity = interface.get_fridge().get_entity(entity_name)
		if entity == None:
			await interface.print("No _" + entity_name + "_ is in the fridge.")
		else:
			await entity.interact(interface, user, arg)
			save_world()

class PokeCommand(Command):
	def __init__(self):
		super().__init__(["poke", "prod"], "Poke a thing in the fridge.", CommandClass.fridge, "The poke command is an alias of _interact [thing], poke_.", "[thing name]", 1)

	async def action(self, interface, user, args=[]):
		thing = " ".join(args)
		await invoke_command(interface, user, "interact", [thing + ",", "poke"])

class PunchCommand(Command):
	def __init__(self):
		super().__init__(["punch"], "Punch a thing in the fridge.", CommandClass.fridge, "The punch command is an alias of _interact [thing], punch.", "[thing name]", 1)

	async def action(self, interface, user, args=[]):
		thing = " ".join(args)
		await invoke_command(interface, user, "interact", [thing + ",", "punch"])

class EatCommand(Command):
	def __init__(self):
		super().__init__(["eat", "consume", "devour", "nom", "chew"], "Eat a thing in the fridge.", CommandClass.fridge, "The eat command is an alias of _interact [thing], eat.", "[thing name]", 1)

	async def action(self, interface, user, args=[]):
		thing = " ".join(args)
		await invoke_command(interface, user, "interact", [thing + ",", "eat"])

class ReadCommand(Command):
	def __init__(self):
		super().__init__(["read"], "Read a thing in the fridge.", CommandClass.fridge, "The read command is an alias of _interact [thing], read.", "[thing name]", 1)

	async def action(self, interface, user, args=[]):
		thing = " ".join(args)
		await invoke_command(interface, user, "interact", [thing + ",", "read"])

class WriteCommand(Command):
	def __init__(self):
		super().__init__(["write", "jot", "scribble", "mark"], "Write something on a thing in the fridge.", CommandClass.fridge, "The write command is an alias of _interact [thing], write {message}.", "[thing name] {, message}", 1)

	async def action(self, interface, user, args=[]):
		thing = " ".join(args)
		if "," in thing:
			thing, message = thing.split(",", 1)
			thing = thing.strip()
			message = " " + message.strip()
		else:
			message = ""
		await invoke_command(interface, user, "interact", [thing + ",", "write" + message])

class CheckCommand(Command):
	def __init__(self):
		super().__init__(["check", "inspect"], "Inspect a thing from the fridge.", CommandClass.fridge, "The check command inspects a thing from the fridge of the channel used to invoke the command.  You can also see if it looks like there is anything stuffed into the thing or not.", "[thing name]", 1)

	async def action(self, interface, user, args=[]):
		entity_name = " ".join(args)
		entity = interface.get_fridge().get_entity(entity_name)
		if entity == None:
			await interface.print("No _" + entity_name + "_ is in the fridge.")
		else:
			content_string = ", ".join(["**" + i.entity_name + "**" for i in entity.contents])
			check_string = entity.check(user) + "\n"
			if len(entity.contents) == 0:
				check_string += "It doesn't look like there is anything stuffed inside of the " + entity.entity_name + "."
			elif len(entity.contents) < 2:
				check_string += "It looks like there might be something stuffed into the " + entity.entity_name + ": " + content_string
			elif len(entity.contents) < 5:
				check_string += "It looks like some things might have been stuffed into the " + entity.entity_name + ": " + content_string
			else:
				check_string += "It looks like the " + entity.entity_name + " is full of things stuffed into it: " + content_string
			await interface.print(check_string)

class StuffCommand(Command):
	def __init__(self):
		super().__init__(["stuff"], "Take something out of your minifridge and stuff it into a thing in the channel fridge.", CommandClass.fridge, "The stuff command takes a thing from your minifridge and stuffs it into another thing in the fridge of the channel used to invoke the command.  You can't stuff an item into itself.  You can optionally pass a number as the first argument to store an amount other than 1 if you have that amount.  The thing and the thing it is being stuffed into must be separated by a comma.", "{amount} [thing name], [container]", 2)

	async def action(self, interface, user, args=[]):
		if to_int(args[0]) != None:
			amount = to_int(args.pop(0))
		else:
			amount = 1
		entity_name = " ".join(args)
		if not "," in entity_name:
			await self.print_usage(interface)
		elif amount <= 0:
			await interface.print("Nothing happened.")
		else:
			entity_name, target = entity_name.split(",", 1)
			entity_name = entity_name.strip()
			target = target.strip()
			if amount != 1:
				if entity_name.endswith("ies"):
					entity_name = entity_name[:-3] + "y"
				elif entity_name.endswith("les"):
					entity_name = entity_name[:-1]
				elif entity_name.endswith("es"):
					entity_name = entity_name[:-2]
				elif entity_name.endswith("s"):
					entity_name = entity_name[:-1]
			count = get_mini_fridge(str(user)).count_entity(entity_name)
			if count == 0:
				await interface.print("No such _" + entity_name + "_ is in " + user.name + "'s minifridge!")
			elif amount > count:
				await interface.print("There are only **" + str(count) + "** of **" + entity_name + "** in " + user.name + "'s minifridge!")
			else:
				fridge = interface.get_fridge()
				target_entity = fridge.get_entity(target)
				if target_entity == None:
					await interface.print("No such _" + target + "_ is in the fridge!")
				elif target_entity.max_contents == 0:
					await interface.print("Things can't be stuffed into the " + target_entity.entity_name + "!")
				elif target_entity.is_full():
					await interface.print("The " + target_entity.entity_name + " is full and won't handle anymore things stuffed into it!")
				else:
					for i in range(amount):
						entity = get_mini_fridge(str(user)).get_entity(entity_name)
						if entity == target_entity:
							await interface.print("The " + entity.entity_name + " can't be stuffed inside of itself.")
							return
						elif not entity.movable:
							await interface.print("The " + entity_name + " is glued inside of the fridge and won't move.")
							return
						entity.put(target_entity)
					if amount == 1:
						determiner_word = "The"
					else:
						determiner_word = str(amount) + " of"
					await interface.print(determiner_word + " " + entity_name + " was taken from " + user.name + "'s minifridge and put in the " + target_entity.entity_name + ".")
					await invoke_command(interface, user, "look")
					save_world()

class UnstuffCommand(Command):
	def __init__(self):
		super().__init__(["unstuff"], "Remove a thing from another thing in the fridge and put it in your own minifridge.", CommandClass.fridge, "The unstuff command takes a thing from another thing in the fridge of the channel used to invoke the command to your minifridge.  You can optionally pass a number as the first argument to take an amount other than 1 if that amount is there.  The thing and the thing it's being taken out of must be separated by a comma.", "{amount} [thing name], [container]", 2)

	async def action(self, interface, user, args=[]):
		if to_int(args[0]) != None:
			amount = to_int(args.pop(0))
		else:
			amount = 1
		entity_name = " ".join(args)
		if not "," in entity_name:
			await self.print_usage(interface)
		elif amount <= 0:
			await interface.print("Nothing happened.")
		else:
			entity_name, target = entity_name.split(",", 1)
			entity_name = entity_name.strip()
			target = target.strip()
			if amount != 1:
				if entity_name.endswith("ies"):
					entity_name = entity_name[:-3] + "y"
				elif entity_name.endswith("les"):
					entity_name = entity_name[:-1]
				elif entity_name.endswith("es"):
					entity_name = entity_name[:-2]
				elif entity_name.endswith("s"):
					entity_name = entity_name[:-1]
			fridge = interface.get_fridge()
			target_entity = fridge.get_entity(target)
			if target_entity == None:
				await interface.print("No such _" + target + "_ is in the fridge!")
			else:
				count = target_entity.count_entity(entity_name)
				if count == 0:
					await interface.print("No such _" + entity_name + "_ is in the " + target_entity.entity_name + "!")
				elif amount > count:
					await interface.print("There are only **" + str(count) + "** of **" + entity_name + "** in the " + target_entity.entity_name + "!")
				else:
					for i in range(amount):
						entity = target_entity.get_entity(entity_name)
						entity.put(get_mini_fridge(str(user)))
					if amount == 1:
						determiner_word = "The"
					else:
						determiner_word = str(amount) + " of"
					await interface.print(determiner_word + " " + entity_name + " was taken from the " + target_entity.entity_name + " and put in " + user.name + "'s minifridge.")
					await invoke_command(interface, user, "look")
					save_world()

class InfoCommand(Command):
	def __init__(self):
		super().__init__(["info", "information", "stats"], "Examine a thing in the fridge.", CommandClass.fridge, "The info command prints known information about a thing in the fridge of the channel used to invoke the command, including its name, its current whereabouts, the name of the user who created it, its age, the name of the last user to interact with it, and, if applicable, how long ago that happened.", "[thing name]", 1)

	async def action(self, interface, user, args=[]):
		entity_name = " ".join(args)
		entity = interface.get_fridge().get_entity(entity_name)
		if entity == None:
			await interface.print("No _" + entity_name + "_ is in the fridge.")
		else:
			await entity.about(interface, user, args[1:])

class AboutCommand(Command):
	def __init__(self):
		super().__init__(["about", "credit", "credits", "fridge", "fridgebot", "creator", "author", "programmer"], "Learn about Fridge Bot!", CommandClass.common, "The about command prints a detailed introduction to Fridge Bot.  Or if you pass an argument, it can also be used an an alias for the _info_ command.", "{thing name}")

	async def action(self, interface, user, args=[]):
		if len(args) > 0:
			await invoke_command(interface, user, "info", args)
		else:
			await interface.print("Fridge Bot is a companion fridge who will safely store all of your _things_!  Fridge Bot provides unique _channel fridges_ that every member of the channel can access as well as _personal minifridges_ for everyone.  Anyone can take things from fridges to put into their personal minifridge, and anyone can take things out of their personal minifridge to store in the channel fridge.\n\nSend the message **" + bot_trigger + "look** and Fridge Bot will display the contents of the _fridge_.  Take a _thing_ from the fridge that you want with the message **" + bot_trigger + "take [name of thing that you want]**.  And put it back in the fridge with the message **" + bot_trigger + "put [name of the thing that you took]**.  Interact with your _personal minifridge_ by talking to Fridge Bot by direct message.\n\nLearn about all of the commands that Fridge Bot knows with the messages **" + bot_trigger + "commands** and **" + bot_trigger + "help**.\n\n_Written in Python with discord.py, Fridge Bot is made with love by MegaLoler/Madeline/Aardbei. <3_")

class IntroCommand(Command):
	def __init__(self):
		super().__init__(["intro", "introduction", "introduce", "hello"], "Allow Fridge Bot to introduce itself.", CommandClass.common)

	async def action(self, interface, user, args=[]):
		await interface.print("Hiii, I'm Fridge Bot.  I store _things_.  If you say **" + bot_trigger + "look** then I'll show you what's in the fridge.  If you say **" + bot_trigger + "take [the name of the thing you want]** then I'll take a thing you want out of the fridge for you to keep for yourself.  And if you say **" + bot_trigger + "put [the name of the thing you took]** then I'll put things back in the fridge for you.\n\nOnce you've collected some things, you can come talk to me through direct message to see your own personal minifridge.\n\nSay **" + bot_trigger + "about** to learn more about me.  And say **" + bot_trigger + "commands** to see what else I know how to do.")

class GrantCommand(Command):
	def __init__(self):
		super().__init__(["grant"], "Grant users new privileges.", CommandClass.admin, "The grant command grants a given user (by user tag name) a new privilege in the form of a command class of commands to be allowed.  Accepted command classes are _common_, _fridge_, and _admin_.", "[user tag name] [command class]", 2)

	async def action(self, interface, user, args=[]):
		user_tag = args[0]
		command_class = command_class_from_string(args[1])
		if command_class == None:
			await interface.print("_" + args[1] + "_ isn't a valid command class.")
		else:
			if command_class in get_permissions(user_tag):
				await interface.print("**" + user_tag + "** already has the privilege **" + command_class.name + "**.")
			else:
				if not user_tag in permissions.keys():
					permissions[user_tag] = ([], [])
				if command_class in standard_permissions:
					permissions[user_tag][1].remove(command_class)
				else:
					permissions[user_tag][0].append(command_class)
				await invoke_command(interface, user, "permissions", [user_tag])
				save_permissions()

class RevokeCommand(Command):
	def __init__(self):
		super().__init__(["revoke"], "Revoke privileges from users.", CommandClass.admin, "The revoke command revokes a privilege in the form of a command class of commands to be allowed from a given user (by user tag name).  Accepted command classes are _common_, _fridge_, and _admin_.", "[user tag name] [command class]", 2)

	async def action(self, interface, user, args=[]):
		user_tag = args[0]
		command_class = command_class_from_string(args[1])
		if command_class == None:
			await interface.print("_" + args[1] + "_ isn't a valid command class.")
		else:
			if not command_class in get_permissions(user_tag):
				await interface.print("**" + user_tag + "** doesn't have the privilege **" + command_class.name + "**.")
			else:
				if not user_tag in permissions.keys():
					permissions[user_tag] = ([], [])
				if command_class in standard_permissions:
					permissions[user_tag][1].append(command_class)
				else:
					permissions[user_tag][0].remove(command_class)
				await invoke_command(interface, user, "permissions", [user_tag])
				save_permissions()

class PermissionsCommand(Command):
	def __init__(self):
		super().__init__(["permissions", "privileges", "ability", "allowed", "level", "class", "classes"], "Display yours or someone else's command invoking privileges.", CommandClass.common, "The permissions command lists the command classes of the commands that you or another user are allowed to invoke.  If you invoke this command without arguments, you can see your own permissions.  Or you can pass the tag of the user to see the permissions of that user instead.\n\nThis command first shows your final effective permissions.  Then it shows which of those permissions you have been granted extra.  Lastly it shows which permissions you have lost.", "{user tag name}")

	async def action(self, interface, user, args=[]):
		if len(args) == 0:
			user_tag = str(user)
		else:
			user_tag = args[0]
		
		final_permissions = get_permissions(user_tag)
		if user_tag in permissions.keys():
			granted_permissions = permissions[user_tag][0]
			lost_permissions = permissions[user_tag][1]
		else:
			granted_permissions = []
			lost_permissions = []
		if len(final_permissions) == 0:
			string = user.name + " is _not allowed to use any commands_, "
		else:
			if len(final_permissions) == 1:
				class_word = "class"
			else:
				class_word = "classes"
			final_string = ", ".join(["**" + cc.name + "**" for cc in final_permissions])
			string = "**" + user_tag + "** is allowed to use commands of " + class_word + " " + final_string + ", "
		if len(granted_permissions) == 0:
			string += "has _not been granted any privileges_, "
		else:
			if len(granted_permissions) == 1:
				privilege_word = "privilege"
			else:
				privilege_word = "privileges"
			granted_string = ", ".join(["**" + cc.name + "**" for cc in granted_permissions])
			string += "has been granted " + privilege_word + " " + granted_string + ", " 
		if len(lost_permissions) == 0:
			string += "has _not lost any privileges_."
		else:
			if len(lost_permissions) == 1:
				privilege_word = "privilege"
			else:
				privilege_word = "privileges"
			lost_string = ", ".join(["**" + cc.name + "**" for cc in lost_permissions])
			string += "has lost " + privilege_word + " " + lost_string + "." 
		await interface.print(string)

# global dictionary of commands
commands = {}

def get_unique_commands():
	unique_commands = []
	for command in commands.values():
		if not command in unique_commands:
			unique_commands.append(command)
	return unique_commands

def add_command(command):
	for alias in command.aliases:
		commands[alias.lower()] = command

async def invoke_command(interface, user, command, args=[]):
	if not command.lower() in commands:
		await interface.print("Fridge Bot doesn't know _" + command + "_, silly!")
	else:
		await commands[command.lower()].invoke(interface, user, args)

# creating and registering command singletons
add_command(TestCommand())
add_command(StoryTestCommand())
add_command(ChannelIdCommand())
add_command(UserIdCommand())
add_command(WorldCommand())
add_command(LookCommand())
add_command(CommandsCommand())
add_command(HelpCommand())
add_command(SpawnCommand())
add_command(DespawnCommand())
add_command(TakeCommand())
add_command(StoreCommand())
add_command(InteractCommand())
add_command(InfoCommand())
add_command(AboutCommand())
add_command(IntroCommand())
add_command(PermissionsCommand())
add_command(GrantCommand())
add_command(RevokeCommand())
add_command(CheckCommand())
add_command(StuffCommand())
add_command(UnstuffCommand())
add_command(PokeCommand())
add_command(PunchCommand())
add_command(EatCommand())
add_command(ReadCommand())
add_command(WriteCommand())

# remove the trigger from the string first
async def parse_command(interface, user, command_string):
	words = command_string.split()
	if len(words) == 0:
		await interface.print("Error parsing command!")
	else:
		await invoke_command(interface, user, words[0], words[1:])

### Interface Stuff ###

class Interface():
	# virtual method
	def read(self):
		return None

	# virtual method
	def print(self, message):
		pass

	# get the local fridge
	# virtual method
	def get_fridge(self):
		return None

	# get permissions
	def get_permissions(self):
		return standard_permissions

class ConsoleInterface(Interface):
	def get_permissions(self):
		return [CommandClass.common, CommandClass.admin]

	def read(self):
		return input()

	def print(self, message):
		print("[CONSOLE] " + message)

	def get_fridge(self):
		return root_entity.get_entity_implicit("Console Fridge")

class DiscordChannelInterface(Interface):
	def __init__(self, channel, user):
		super().__init__()
		self.channel = channel
		self.user = user

	async def read(self, content=None, check=None):
		response = await client.wait_for_message(author=self.user, channel=self.channel, content=content, check=check)
		ignore_messages.append(response)
		return response.content

	async def print(self, message):
		if len(message) > max_message_length:
			first = message
			rest = ""
			while len(first) > max_message_length:
				first, last = first.rsplit("\n", 1)
				rest = "\n" + last + rest
			await client.send_message(self.channel, first)
			await self.print(rest[1:])
		else:
			await client.send_message(self.channel, message)

	def get_fridge(self):
		if self.channel.is_private:
			return get_mini_fridge(str(self.user))
		else:
			return get_channel_fridge(str(self.channel.server), str(self.channel))

	def get_permissions(self):
		return get_permissions(self.user)

# interface singletons
console_interface = ConsoleInterface()

### Console Interface ###

# ok honestly, i have _no clue_ how coroutines work, so i dunno how to make this work

def console_interface_loop():
	while not client.is_closed:
		parse_command(console_interface, None, input("> "))

### Discord Stuff ###

client = discord.Client()

@client.event
async def on_ready():
    print("Connected as user " + client.user.name + " with id " + client.user.id + ".")

@client.event
async def on_message(message):
	if logging: log(message)
	if message in ignore_messages:
		ignore_messages.remove(message)
	elif client.user.id != message.author.id:
		command_string = None
		if message.content.startswith(bot_trigger):
			command_string = message.content[1:]
		elif message.channel.is_private:
			command_string = message.content
		if command_string != None:
			await parse_command(DiscordChannelInterface(message.channel, message.author), message.author, command_string)

@client.event
async def on_message_edit(before, after):
	if logging: log(after)

def get_token():
	with open(token_file, "r", encoding='UTF-8') as f:
		return f.read().strip()

if __name__ == "__main__":
	init_world()
	init_permissions()
	client.run(get_token())
