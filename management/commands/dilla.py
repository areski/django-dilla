from decimal import Decimal
from django.core.exceptions import ValidationError
import random, string, datetime, os
from optparse import make_option
from django.contrib.webdesign.lorem_ipsum import words,paragraphs
from django.core.management.base import BaseCommand
from django.db.models import get_app,get_models
from django.conf import settings

__author__="""Adam Rutkowski <adam@HELLOSPAMBOT.mtod.org>"""
__doc__="""Dilla for Django is a command extension tool that populates your database with randomized data.
For further information visit Dilla home at http://code.google.com/p/django-dilla
"""

"""
Here's what can be done in models now:
models.py:

class DillaController():
	#this defines the order of how models are populated.
	#so that errors don't happen because of cross model relationships where
	#no data is ready in either model
	#(Optional)
	models=('UserProfile','Venue','Event','Genre','Artist')

class Event(models.Model):
	venue=models.ForeignKey('Venue')
	artists=models.ManyToManyField('Artist')
	date=models.DateTimeField(blank=False,null=False)
	showtime=models.TimeField(blank=False,null=False)
	doortime=models.TimeField(blank=False,null=False)
	covercharge=models.DecimalField(decimal_places=2,max_digits=7)
	created_at=antaresia_models.ModelCommons.created_at()
	updated_on=antaresia_models.ModelCommons.updated_on()
	#usual Dilla meta class
	class Dilla():
		skip_model=False
		generate_images=False
		image_fields=None
		image_resolution="1024x768" #if images, this resolution
		image_resolutions=('300x340','200x190','100x10','200x90') #if images, use a random resolution from this tuple
		field_extras={ #field extras are for defining custom dilla behavior per field
			'fieldname':{
				'generator':None, #can point to a callable, which must return the desired value
				'generator_wants_extras':False, #whether or not to pass this "field extra" hash item to the callable
				'random_values':("word","yes","no","1"), #choose a random value from this tuple
				'image_size':'1024x768', #if images, use this image size for this field
				'image_sizes':('300x340','200x190','100x10','200x90'), #if images, use a random size from this tuple
				'max':10, #for many to many fields, the maximum associated objects will be 10, so it will take a range like: Model.objects.all().order_by("?")[0:random.randrange(0,max)]
			},
			'anotherfieldname':{...}
		}

"""

image_support=False
try:#pil dependency checking
	import Image,ImageDraw,ImageFont
	ROOT=os.path.split(__file__)[0]
	FAKE_UPLOAD_RELATIVE="dilla-fakes/"
	FAKE_UPLOAD_PATH="%s%s"%(settings.MEDIA_ROOT,FAKE_UPLOAD_RELATIVE)
	#armn(Apple Roman),ADBE(Adobe Expert),ADOB(Adobe Standard),symb(Microsoft Symbol),unic(Unicode),armn(TTF_ENCODING)
	TTF_ENCODING=getattr(settings,'TTF_ENCODING','armn')
	if not os.path.exists(FAKE_UPLOAD_PATH):os.makedirs(FAKE_UPLOAD_PATH)
	#all the fonts downloaded from dafont.com and licensed `FREE`)
	fonts=['Besmellah_1.ttf','skullz.ttf','bonohadavision.ttf','openlogos.ttf', 'invaders.from.space.[fontvir.us].ttf','anim____.ttf']
	image_support=True
except ImportError, e:
	print 'Images not supported, something went wrong: %s' % e
    
confirm_message="""Are you sure you want to run Dilla? 
It will add a lot of random data to your database %s@%s.
Type 'yes' to confirm.
"""%(settings.DATABASE_USER,settings.DATABASE_NAME)

class Command(BaseCommand):
	requires_model_validation=True
	output_transaction=True
	help=__doc__
	args='appname [appname ...]'
	option_list=BaseCommand.option_list+(
		make_option('--iter', '-i', default='20', action='store', dest='iterations',help='Number of iterations per model. Default is 20.'),
		make_option('--no-doubt', '-n', action='store_true', dest='no_doubt',help='Always fill fields that can be blank. Do not randomly decide.'),
	)
	
	def handle(self,*app_labels,**options):
		if not settings.DEBUG:
			confirm=raw_input(confirm_message)
			if confirm != 'yes': return
		models=[]
		for a in app_labels:
			app=get_app(a)
			if hasattr(app,"DillaController"):
				if hasattr(app.DillaController,"models"):
					for model in app.DillaController.models:
						if hasattr(app,model): models.append(getattr(app,model))
						else: print "Model " + model + " not found."
			else: models.extend(get_models(app))
		instances_by_model={}
		for model in models:
			dilla=None
			if not instances_by_model.get(model,None):instances_by_model[model]=[]
			if hasattr(model,'Dilla'):dilla=model.Dilla
			if dilla and getattr(dilla,'skip_model',False):continue
			for i in range(int(options['iterations'])):
				instance=model()
				for field in model._meta.fields:
					if not field.auto_created:
						if not field.blank or options['no_doubt'] or hasattr(field,"auto_now") or hasattr(field,"auto_now_add"):
							self.fill(field=field,obj=instance,dilla=dilla)
						elif field.blank:
							self._decide(self.fill,field=field,obj=instance,dilla=dilla)
				instance.save()
				instances_by_model[model].append(instance)
		for model in models: #go back through each model, and alter each instance's many to many fields
			instances_list=instances_by_model[model]
			self.many_to_manys(model,instances_list,dilla)

	def many_to_manys(self,model,instances,dilla=None):
		many_to_manys=model._meta.many_to_many
		for instance in instances:
			for many_to_many_field in many_to_manys:
				max=5
				name=many_to_many_field.name
				if dilla and hasattr(dilla,"field_extras"):
					field_extras=dilla.field_extras.get(name,None)
					if field_extras: max=field_extras.get("max",5)
				ml=many_to_many_field.rel.to
				objects=ml.objects.all().order_by("?")
				count=objects.count()
				end=random.randrange(0,max)
				if count<end:relobjs=objects[0:count]
				else: relobjs=objects[0:end]
				setattr(instance,name,relobjs)
				instance.save
	
	def allow_spaces(self,field_extras=None):
		if not field_extras: return True
		return field_extras.get("spaces",True)
	
	def generate_URLField(self,**kwargs):
		urls=(
			"http://www.google.com/","http://www.amazon.com/","http://www.digg.com/",
			"http://www.nba.com/","http://www.espn.com/","http://www.python.org/",
		)
		urls=getattr(settings,"DILLA_URLS",urls)
		return urls[random.randrange(0,len(urls))]
	
	def generate_CharField(self,**kwargs):
		salt=""
		if kwargs.get('unique',False): salt="".join([random.choice(string.digits) for i in range(random.randint(1,16))])
		result="%s %s" % (words(random.randint(1,4),common=False),salt)
		max_length=kwargs.get('max_length',None)
		length=len(result)
		if max_length and length > max_length: result=result[length-max_length:] #chop off too many chars for max length
		if not self.allow_spaces(kwargs.get("field_extras",False)):result=result.replace(" ","")
		return result
	
	def generate_TextField(self,**kwargs):
		result="\n".join(paragraphs(random.randint(1,3)))
		if not self.allow_spaces(kwargs.get("field_extras",False)): result=result.resplace(" ","")
		return
	
	def generate_DecimalField(self,**kwargs):
		return Decimal(str(random.random()+random.randint(1,20)))
	
	def generate_IntegerField(self,**kwargs):
		return random.randint(1,255)
	
	def generate_TimeField(self,**kwargs):
		today=datetime.datetime.now()
		return datetime.time(today.hour,today.minute,today.second)
	
	def generate_DateTimeField(self,**kwargs):
		return datetime.datetime.now()  
	
	def generate_DateField(self,**kwargs):
		return datetime.datetime.now()
	
	def generate_ForeignKey(self, **kwargs):
		field=kwargs.get('field',None)
		if not field: return None
		kls=field.rel.to
		try: #try to randomly select from existing models
			related_object=kls.objects.all().order_by('?')[0]
			return related_object
		except IndexError:
			print "Couldn't find related object of %s. Lack of further implementation." % kls
			return None
	
	def generate_SlugField(self,**kwargs):
		return self.generate_CharField(**kwargs).replace(" ","_")
	
	def generate_BooleanField(self,**kwargs):
		return bool(random.randint(0,1))
	
	def _decide(self,action,*args,**kwargs):
		if bool(random.randint(0,1)):return action(*args,**kwargs)
	
	def _generate_image(self, resolution):
		assert image_support
		size=map(int,resolution.split('x'))
		im=Image.new('RGB',size)
		draw=ImageDraw.Draw(im)
		def _gen_rgb():
			return "rgb%s" % str(tuple([random.randint(0,255) for i in range(3)]))    
		text_pos=(0,0)
		text=[random.choice(string.letters) for i in range(2)]
		draw.rectangle([(0,0),tuple(size)],fill=_gen_rgb())
		for i in range(2):
			fontfile = random.choice(fonts)
			font = ImageFont.truetype("%s/fonts/%s" % (ROOT, fontfile), size[0], encoding=TTF_ENCODING)                                         
			draw.text(text_pos, text[i],fill=_gen_rgb(),font=font)
			del font
		filename="%s.png" % self.generate_SlugField(unique=True)
		im.save("%s%s"%(FAKE_UPLOAD_PATH,filename),'PNG')
		del draw,im
		return "%s%s"%(FAKE_UPLOAD_RELATIVE,filename)
	
	def fill(self,field,obj,dilla=None):
		val=None
		field_extras=None
		if dilla:
			field_extras=getattr(dilla,'field_extras',None)
			if field_extras:field_extras=field_extras.get(field.name,None)
			skip_fields=getattr(dilla,'skip_fields',None)
			if skip_fields and field.name in skip_fields:
				print 'Skipping field: %s' % field.name
				return
			if field_extras and field_extras.get("random_values",None):
				vals=field_extras.get('random_values')
				val=vals[random.randrange(0,len(vals))]
			image_fields=getattr(dilla,'image_fields',None)
			generate_images=getattr(dilla,'generate_images',False)
			if image_fields and generate_images and field.name in image_fields:
				resolution=getattr(obj.Dilla,'image_resolution','640x480')
				resolutions=getattr(obj.Dilla,'image_resolutions',None)
				if resolutions:
					resolution=obj.Dilla.image_resolutions[random.randrange(0,len(obj.Dilla.image_resolutions))]
				if field_extras:
					resolution=field_extras.get("image_size","800x600")
					if field_extras.get("image_sizes",None):
						sizes=field_extras.get("image_sizes",None)
						if sizes: resolution=sizes[random.randrange(0,len(sizes))]
					else: resoluteion="800x600"
				if(image_support):val=self._generate_image(resolution)
		if field_extras:
			generator=field_extras.get("generator",None)
			if callable(generator):
				if field_extras.get("generate_wants_extras",None):val=generator(field_extras)
				else: val=generator()
		if not val:
			internal_type=field.get_internal_type()
			if hasattr(self,"generate_%s"%internal_type):
				generate_method=getattr(self,"generate_%s"%internal_type)
				val=generate_method(field=field,unique=field.unique,max_length=field.max_length,field_extras=field_extras)
		setattr(obj,field.name,val)