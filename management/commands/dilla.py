import random,string,datetime,os,re,time
from decimal import Decimal
from django.core.exceptions import ValidationError
from optparse import make_option
from django.contrib.webdesign.lorem_ipsum import words,paragraphs
from django.core.management.base import BaseCommand
from django.db.models import get_app,get_models,URLField
from django.conf import settings

if settings.DATABASE_ENGINE == 'postgresql_psycopg2':
    import psycopg2
    IntegrityError = psycopg2.IntegrityError
elif settings.DATABASE_ENGINE == 'postgresql_psycopg2':
    import MySQLdb
    IntegrityError = MySQLdb.IntegrityError
else:
    # XXX: BAD
    IntegrityError = Exception

#authors:
#adam rutkowski <adam@mtod.org>
#aaron smith <aaron@macendeavor.com>

"""
EXAMPLE
models.py:

class DillaController():
    #(Optional) this defines the order of how models are populated. (Fixes cross ForeignKey problems)
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
        resolution="1024x768" #if images, this resolution
        resolutions=('300x340','200x190','100x10','200x90') #if images, use a random resolution from this tuple
        field_extras={ #field extras are for defining custom dilla behavior per field
            'fieldname':{
                'generator':None, #can point to a callable, which must return the desired value. If this is a string, it looks for a method in the dilla.py file.
                'generator_wants_extras':False, #whether or not to pass this "field extra" hash item to the callable
                'random_values':("word","yes","no","1"), #choose a random value from this tuple
                'resolution':'1024x768', #if images, use this image size for this field
                'resolutions':('300x340','200x190','100x10','200x90'), #if images, use a random size from this tuple
                'max':10, #for many to many fields, the maximum associated objects will be 10, so it will take a range like: Model.objects.all().order_by("?")[0:random.randrange(0,max)]
                'spaces':False, #if Char/TextField, whether or not to allow spaces
                'word_count':1, #if Char/TextField, the number of words to generate
                'word_range':(3,7), #a range of words to generate (3-7 words)
                'paragraph_count:1, #if TextField, the number of paragraphs to generate
                'paragraph_range':(3,5), #a range of paragraphs to generate (3 - 5 paragraphs)
                'integer_range':(0,2), #a range for any integer type field (IntegerField,SmallIntegerField,PositiveInteger,PositiveSmallInteger)
                #TODO:'digits_only':True, #if Char/TextField, but want numbers only
                #TODO:'digit_range:(30,400), #a range for digit only creation (default range is (0,9999))
                #TODO:'digit_ranges':((0,20),(30,300)), #chooses random range from this tuple.
                #TODO:'digits_for_words':False|True (Default:False) #generates lipsum words, but then replaces each word with numbers. (like a sentance of numbers)
            },
            'anotherfieldname':{...}
        }

"""

image_support=False
try:
    import Image,ImageDraw,ImageFont
    ROOT=os.path.split(__file__)[0]+"/../"
    FAKE_UPLOAD_RELATIVE="dilla-fakes/"
    FAKE_UPLOAD_PATH="%s%s"%(settings.MEDIA_ROOT,FAKE_UPLOAD_RELATIVE)
    #armn(Apple Roman),ADBE(Adobe Expert),ADOB(Adobe Standard),symb(Microsoft Symbol),unic(Unicode),armn(TTF_ENCODING)
    TTF_ENCODING=getattr(settings,'TTF_ENCODING','armn')
    if not os.path.exists(FAKE_UPLOAD_PATH):os.makedirs(FAKE_UPLOAD_PATH)
    fonts=['Besmellah_1.ttf','skullz.ttf','bonohadavision.ttf','openlogos.ttf', 'invaders.from.space.[fontvir.us].ttf','anim____.ttf']
    image_support=True
except ImportError, e:
    print 'Images not supported, something went wrong: %s' % e
    
confirm_message="""Are you sure you want to run Dilla? 
It will add a lot of random data to your database %s@%s.
Type 'yes' to confirm.
"""%(settings.DATABASE_USER,settings.DATABASE_NAME)

class Command(BaseCommand):
    """
    Dilla is a command that populates your database with randomized data. (http://gitweb.codeendeavor.com/?p=dilla.git;a=summary)

    Examples:
    1. Generate data for all models in an app
       >>python manage.py dilla app_name
    
    2. Generate data for all models in all apps listed
       >>python manage.py dilla app_name app_name
    
    3. Generate data for all models in all apps listed (an alternative to #2)
       >>python manage.py dilla -a app_name -a app_name
    
    4. Generate data for supplied models, in the supplied apps
       >>python manage.py dilla -a app_name -m ModelName
    
    5. Addition to #4, generate data for multiple models
       >>python manage.py dilla -a app_name -m ModelName -m AnotherModelName
    
    ** The order of app names and model names are important, if a model has
       a ForeignKey to another model, but there isn't data available yet
       in the foregn table, problems occur.
    
    ** When using -a or -m, you don't need to use full python path.
    """
    requires_model_validation=True
    output_transaction=True
    help=__doc__
    args='appname [appname ...]'
    option_list=BaseCommand.option_list+(
        make_option('--iter','-i',default='20',action='store',dest='iterations',help='Number of iterations per model. Default is 20.'),
        make_option('--no-doubt','-n',action='store_true',dest='no_doubt',help='Always fill fields that can be blank. Do not randomly decide.'),
        make_option('--app','-a',action='append',dest='apps',help='Generate data for these apps.'),
        make_option('--model','-m',action='append',dest='models',help='Generate data for these models.'),
    )
    
    def handle(self,*app_labels,**options):
        """
        Main execution point
        """
        if not settings.DEBUG:
            confirm=raw_input(confirm_message)
            if confirm != 'yes': return
        models=[]
        model_labels=[]
        apps=[]
        if app_labels and len(app_labels)>0: apps.extend(app_labels)
        if options.get("apps",False): apps.extend(options.get("apps"))
        if options.get("models",False): model_labels.extend(options.get("models"))
        for a in apps:
            app_label=a
            app=get_app(a)
            if len(model_labels)>0:
                app_models=get_models(app)
                for app_model in app_models:
                    meta=app_model._meta
                    for model_label in model_labels:
                        if meta.object_name==model_label and meta.app_label==app_label:
                            models.append(app_model)
            elif hasattr(app,"DillaController"):
                if hasattr(app.DillaController,"models"):
                    for model in app.DillaController.models:
                        if hasattr(app,model): models.append(getattr(app,model))
                        else: print "Model " + model + " not found."
            else:
                models.extend(get_models(app))
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
                try:
                    instance.save()
                    #if field has unique, this error will be thrown, in the case of dilla, we don't care
                except IntegrityError:
                    instance=None
                    continue
                instances_by_model[model].append(instance)
        for model in models: #go back through each model, and alter each instance's many to many fields
            if len(model._meta.many_to_many) <= 0: continue
            instances_list=instances_by_model[model]
            dilla=getattr(model,'Dilla',False)
            self.many_to_manys(model,instances_list,dilla)

    def _get_field_option(self,field_extras,option_name,default):
        """
        Shortcut to get a field option
        self._get_field_option(field_option,"spaces",True)
        """
        if not field_extras: return default
        return field_extras.get(option_name,default)

    def hashkey(self,**kwargs):
        """
        Gererates an md5 hashkey. Use this with the 'generator' key, EX:
        field_extras={
            'myfield':{
                'generator':'hashkey'
            }
        }
        """
        import md5
        m=md5.new()
        m.update(str(time.clock()))
        m.update(str(random.random()))
        m.update(str(random.random()))
        m.update(settings.SECRET_KEY)
        return m.hexdigest()

    def uuid(self,**kwargs):
        """
        Generates a uuid, EX:
        field_extras={
            'myfield':{
                'generator':'uuid'
            }
        }
        """
        import uuid
        return str(uuid.uuid1())

    def extended_zip(self,**kwargs):
        """
        Generates an extended zip code (94109-4382) EX:
        field_extras={
            'myfield':{
                'generator':'extended_zip'
            }
        }
        """
        int1=random.randint(11111,99999)
        int2=random.randint(1111,9999)
        return str(int1)+"-"+str(int2)

    def zip(self,**kwargs):
        """
        Generates a zip code (94109) EX:
        field_extras={
            'myfield':{
                'generator':'zip'
            }
        }
        """
        int1=random.randint(11111,99999)
        return str(int1)


    def many_to_manys(self,model,instances,dilla=None):
        """
        Creates data for many to many fields
        """
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
    
    def generate_PositiveIntegerField(self,**kwargs):
        """
        Generates a PositiveIntegerField value.
        Supported field extras:
        field_extras={
            'myfield':{
                'integer_range':(0,10) #specify the integer range to generate
            }
        }
        """
        field_extras=kwargs.get("field_extras",False)
        ranj=self._get_field_option(field_extras,"integer_range",(0,32))
        if len(ranj)<2:ranj=(0,32)
        if ranj[0]<0 or ranj[1]<0:
            print "PositiveInteger ranges cannot be less than zero, defaulting to range(0,32)"
            ranj=(0,32)
        return random.randint(ranj[0],ranj[1])
    
    def generate_PositiveSmallIntegerField(self,**kwargs):
        """
        Generates a PositiveSmallIntegerField value.
        Supported field extras:
        field_extras={
            'myfield':{
                'integer_range':(0,10) #specify the integer range to generate
            }
        }
        """
        field_extras=kwargs.get("field_extras",False)
        ranj=self._get_field_option(field_extras,"integer_range",(0,32))
        if len(ranj)<2:ranj=(0,32)
        if ranj[0]<0 or ranj[1]<0:
            print "PositiveSmallInteger ranges cannot be less than zero, defaulting to range(0,32)"
            ranj=(0,32)
        return random.randint(ranj[0],ranj[1])
    
    def generate_SmallIntegerField(self,**kwargs):
        """
        Generates a SmallIntegerField value.
        Supported field extras:
        field_extras={
            'myfield':{
                'integer_range':(0,10) #specify the integer range to generate
            }
        }
        """
        field_extras=kwargs.get("field_extras",False)
        ranj=self._get_field_option(field_extras,"integer_range",(0,32))
        if len(ranj)<2:ranj=(0,32)
        return random.randint(ranj[0],ranj[1])
    
    def generate_URLField(self,**kwargs):
        """
        Returns a random URL for URLFields. By default there's only a few urls,
        but you can specify your own list of urls to choose from in settings.
        settings.DILLA_URLS=('http://www.google.com/','http://www.whitehouse.com',)
        """
        urls=(
            "http://www.google.com/","http://www.amazon.com/","http://www.digg.com/",
            "http://www.nba.com/","http://www.espn.com/","http://www.python.org/",
        )
        urls=getattr(settings,"DILLA_URLS",urls)
        return urls[random.randrange(0,len(urls))]
    
    def generate_IPAddressField(self,**kwargs):
        """
        Generates a random IP Address
        """
        ip=str(random.randrange(0,255))+"."+str(random.randrange(0,255))+"."+str(random.randrange(0,255))+"."+str(random.randrange(0,255))
        return ip
        
    def generate_CharField(self,**kwargs):
        """
        Generates char data for any CharField.
        Supported field extras:
        field_extras={
            'myfield':{
                'spaces':False|True, #(Default: True) #whether or not to allow spaces
                'word_count':3, #if specified, only 3 words will be generatd, if not specified, random between 1 and 4.
                'word_range:(2,5), #if specified, overrides the 'word_count' option, and will generate 2-5 random words.
            }
        }
        """
        salt=""
        field_extras=kwargs.get("field_extras",False)
        if kwargs.get('unique',False): salt="".join([random.choice(string.digits) for i in range(random.randint(1,16))])
        word_count=self._get_field_option(field_extras,'word_count',-1)
        word_range=self._get_field_option(field_extras,'word_range',-1)
        if isinstance(word_range,tuple) and len(word_range)>1:
            result="%s %s" % (words(random.randint(word_range[0],word_range[1]),common=False),salt)
        elif word_count > 0:
            result="%s %s" % (words(word_count,common=False),salt)
        else:
            result="%s %s" % (words(random.randint(1,4),common=False),salt)
        max_length=kwargs.get('max_length',None)
        length=len(result)
        if max_length and length > max_length: result=result[length-max_length:] #chop off too many chars for max length
        if not self._get_field_option(field_extras,"spaces",True) and word_count == -1 and word_range == -1:
            result=result.replace(" ","")
        result=re.sub(r' $','',result)
        return result
    
    def generate_TextField(self,**kwargs):
        """
        Generates text data for any TextField.
        Supported field extras:
        field_extras={
            'myfield':{
                'spaces':False|True, #(Default: True) #whether or not to allow spaces
                'paragraph_count':3, #The number of paragraphs to generate.
                'paragraph_range':(2,8) #A range for the number of paragraphs to generate - random between this range.
            }
        }
        """
        field_extras=kwargs.get("field_extras",False)
        paragraph_count=self._get_field_option(field_extras,'paragraph_count',-1)
        paragraph_range=self._get_field_option(field_extras,'paragraph_range',-1)
        if isinstance(paragraph_range,tuple) and len(paragraph_range)>1:
            result="\n".join(paragraphs(random.randint(paragraph_range[0],paragraph_range[1])))
        elif paragraph_count > 0:
            result="\n".join(paragraphs(paragraph_count))
        else:
            result="\n".join(paragraphs(random.randint(1,3)))
        if not self._get_field_option(field_extras,'spaces',True): result=result.resplace(" ","")
        result=re.sub(r' $','',result)
        return result
    
    def generate_DecimalField(self,**kwargs):
        """
        Generates a random decimal number
        """
        return Decimal(str(random.random()+random.randint(1,20)))
    
    def generate_IntegerField(self,**kwargs):
        """
        Generates a random integer
        """
        return random.randint(1,255)
    
    def generate_TimeField(self,**kwargs):
        """
        Generates time object for TimeField's
        """
        today=datetime.datetime.now()
        return datetime.time(today.hour,today.minute,today.second)
    
    def generate_DateTimeField(self,**kwargs):
        """
        Generates datetime for DateTimeField's
        """
        return datetime.datetime.now()  
    
    def generate_DateField(self,**kwargs):
        """
        Generates datetime for DateField's
        """
        return datetime.datetime.now()
    
    def generate_ForeignKey(self, **kwargs):
        """
        Finds a random foreign related object.
        """
        field=kwargs.get('field',None)
        if not field: return None
        kls=field.rel.to
        try:
            related_object=kls.objects.all().order_by('?')[0]
            return related_object
        except IndexError:
            print "Couldn't find a related object for ForeignKey: %s" % field.name
            return None
    
    def generate_SlugField(self,**kwargs):
        """
        Generates a slug for SlugField's
        """
        result=self.generate_CharField(**kwargs).replace(" ","_")
        result=re.sub(r'_$',"",result)
        return result
    
    def generate_BooleanField(self,**kwargs):
        """
        Generates a boolean for BooleanField's
        """
        return bool(random.randint(0,1))
    
    def generate_EmailField(self,**kwargs):
        """
        Generates a random lipsum email address.
        """
        front=words(1,common=False)
        back=words(1,common=False)
        #side to side
        email=front+"@"+back+".com"
        return email
    
    def _decide(self,action,*args,**kwargs):
        """
        Decides whether or not to give a blank field a value
        """
        if bool(random.randint(0,1)):return action(*args,**kwargs)
    
    def _generate_image(self, resolution):
        """
        Generates image
        """
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
            fontfile=random.choice(fonts)
            font=ImageFont.truetype("%s/fonts/%s" %(ROOT,fontfile), size[0],encoding=TTF_ENCODING)
            draw.text(text_pos, text[i],fill=_gen_rgb(),font=font)
        filename="%s.png" % self.generate_SlugField(unique=True)
        im.save("%s%s"%(FAKE_UPLOAD_PATH,filename),'PNG')
        return filename
    
    def fill(self,field,obj,dilla=None):
        """
        Does the work to fill model instances with random data
        """
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
                resolution=getattr(obj.Dilla,'resolution','640x480')
                resolutions=getattr(obj.Dilla,'resolutions',None)
                if resolutions:
                    resolution=obj.Dilla.resolutions[random.randrange(0,len(obj.Dilla.resolutions))]
                if field_extras:
                    resolution=field_extras.get("resolution","800x600")
                    if field_extras.get("resolutions",None):
                        sizes=field_extras.get("resolutions",None)
                        if sizes: resolution=sizes[random.randrange(0,len(sizes))]
                    else: resolution="800x600"
                if(image_support):val=self._generate_image(resolution)
        if field_extras:
            generator=field_extras.get("generator",None)
            if callable(generator):
                if field_extras.get("generator_wants_extras",None):val=generator(field_extras)
                else: val=generator()
            elif isinstance(generator,str):
                if hasattr(self,generator):
                    method=getattr(self,generator)
                    val=method()
        if not val:
            internal_type=field.get_internal_type()
            if isinstance(field,URLField):
                val=self.generate_URLField(field=field,unique=field.unique,max_length=field.max_length,field_extras=field_extras)
            elif hasattr(self,"generate_%s"%internal_type):
                generate_method=getattr(self,"generate_%s"%internal_type)
                val=generate_method(field=field,unique=field.unique,max_length=field.max_length,field_extras=field_extras)
        setattr(obj,field.name,val)
