import xml.etree.ElementTree as ET
import time
import random

class XmlParse(object):
    def __init__(self, xmlfile):
        self.xmlfile = xmlfile

    def xmlparse_file(self):
        tree = ET.parse(self.xmlfile)
        root = tree.getroot()
        data = {float(node.attrib['p'].split(',')[:4][0]) : node.attrib['p'].split(',')[:4] + [node.text] for node in root if node.tag == 'd'}
        return data

    # FIXME:
    @staticmethod
    def xmlparse_content(xmlcontent):
        root = ET.fromstring(xmlcontent)
        data = {float(node.attrib['p'].split(',')[:4][0]) : node.attrib['p'].split(',')[:4] + [node.text] for node in root if node.tag == 'd'}
        return data

    @staticmethod
    def sort(xmldata):
        dkey_list = list(map(float,xmldata.keys()))
        dkey_list.sort()
        sorteddata = [xmldata[index] for index in dkey_list]
        return sorteddata
    
    @staticmethod
    def extract(xmldata):
        for data in xmldata:
            st_time = data[0]
            st_type = data[1]
            st_fontsize = data[2]
            st_color_temp = str(hex(int(data[3]))).upper()
            st_color = st_color_temp[-2:] + st_color_temp[4:6] + st_color_temp[2:4]
            st_text = data[4]
            yield {'st_time':st_time, 'st_type':st_type, 'st_fontsize':st_fontsize, 'st_color':st_color, 'st_text':st_text}


class GenerateAss(object):
    def __init__(self, assfile, xml, resx=None, resy=None):
        self.assfile = assfile
        if '.xml' in xml:
            xmldata = XmlParse(xml).xmlparse_file()
        else:
            xmldata = XmlParse.xmlparse_content(xml)
        sorteddata = XmlParse.sort(xmldata)
        self.g_xmldata = XmlParse.extract(sorteddata)
        
        if not resx:
            self.resx = 1920
        else:
            self.resx = resx
        if not resy:
            self.resy = 1080
        else:
            self.resy = resy

        self.speed = 5

    def writeass(self, data):
        with open(self.assfile, 'a',encoding = 'utf-8') as file:
            file.write(data)

    def scriptinfo(self):
        start = '[Script Info]\n'
        comment = ';\n;\n'
        title = 'Tile:\n'
        original_script = 'Original Script:\n'
        update_details = 'Update Details:\n'
        script_type = 'ScriptType: V4.00+\n'
        collisions = 'Collisions: Normal\n'
        playresx = 'PlayResX: {}\n'.format(self.resx)
        playresy = 'PlayResY: {}\n'.format(self.resy)
        timer = 'Timer: 100\n'
        return ''.join([
                        start, comment, title, original_script, update_details, script_type,
                        collisions, playresx, playresy, timer])

    def v4style(self,styles):
        title = '[V4+ Styles]\n'
        style_format = 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
        default_style = self.genv4style('Default','&H00FFFFFF')
        return ''.join([title,style_format,default_style,styles])
        
    
    @staticmethod
    def genv4style(name,color):
        return 'Style: {},Microsoft YaHei,30,{},&H0000FFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,7,0,0,0,1\n'.format(name,color)
    
    def events(self, events):
        title = '[Events]\n'
        events_format = 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
        return ''.join([title,events_format,events])

    @staticmethod
    def genevents(layer,duration,style,pos,effect,text):
        return 'Dialogue: {},{},{},,{},{},{}\n'.format(layer,duration,style,pos,effect,text)

    def parsexmldata(self):
        styles,events,st_pos = [],[],{}
        # FIXME:
        for xmldata in self.g_xmldata:
            if xmldata['st_color'] != 'FFFFFF':
                st_color = xmldata['st_color']
                stylename = 'Color' + st_color
                styles.append(self.genv4style(stylename,'&H00' + st_color))
            else:
                stylename = 'Default'
            
            delay = self.speed

            st_time = xmldata['st_time'].split('.')
            start = int(st_time[0])
            end = int(st_time[0]) +  delay * (self.resx + 500) / 1000
            
            if int(xmldata['st_type']) > 3:
                effect = ''
                layer = 1
                end = int(st_time[0]) + 5
            else:
                effect ='Banner;{}'.format(delay) 
                layer = 0

            time_p1 = time.strftime("%H:%M:%S",time.gmtime(start))[1:]
            time_p2 =  time.strftime("%H:%M:%S",time.gmtime(end))[1:]
            time_p3 = st_time[1][:2]
            st_start = '.'.join([time_p1, time_p3])
            st_end = '.'.join([time_p2, time_p3])
            duration = ','.join([st_start,st_end])
            text = xmldata['st_text'] 
            appearing = float(xmldata['st_time'])
            # Magic 25-font_width
            appeared = appearing + delay * 25 * len(text) / 1000
            marginV = random.randrange(0,self.resy -30 ,30)
            if int(xmldata['st_type']) <= 3:
                while True:
                    try:
                        if appearing > st_pos[marginV]:
                            st_pos.update({marginV:appeared})
                            break
                        else:
                            marginV = random.randrange(0,self.resy - 30,30) 
                    except KeyError:
                        st_pos.update({marginV:appeared})
                        break
            pos = '{0},{0},{1}'.format(int(self.resx / 2 - 25 * len(text) / 2),marginV)
            events.append(self.genevents(layer,duration,stylename,pos,effect,text))
        return ''.join([self.v4style(''.join(styles)),self.events(''.join(events))])



    def run(self):
        self.writeass(self.scriptinfo() + self.parsexmldata())
        