"""
FacebookTools.py
Author: Stephen J. Sekula
Created: Mar. 13, 2013

* FacebookHandler:
Inherits from: SocialHandler
Purpose: to gather messages from a Facebook instance, and write messages to
the same instance. It uses FBCMD to do its work.
"""

from SocialHandler import *
import sys

import subprocess
import os
import re
import datetime
import calendar
import commands
import unicodedata

from MessageObj import Message


class FacebookHandler(SocialHandler):
    """ a class to read and post to a Facebook feed """
    def __init__(self,username="",sharelevel="Public",album="latest"):
        SocialHandler.__init__(self)
        self.sharelevel = sharelevel
        self.album = album

        
        # check that fbcmd is installed
        self.active = True
        if self.which('fbcmd') == None:
            self.msg(0,unicode("fbcmd not installed; Facebook handler will be inactive"))
            self.active = False
            pass

        pass
 


    def gather(self):
        if not self.active:
            return []

        self.msg(0, self.texthandler("Gathering messages."))

        self.messages = []

        # enforce printing of date and formatting of date
        commands.getoutput('fbcmd SAVEPREF -stream_dateformat=\'Y D M d H:i Z\'')
        commands.getoutput('fbcmd SAVEPREF -stream_show_date=1')
        commands.getoutput('fbcmd SAVEPREF -pic_dateformat=\'Y D M d H:i Z\'')
        commands.getoutput('fbcmd SAVEPREF -pic_show_date=1')
        commands.getoutput('fbcmd SAVEPREF -stream_show_attachments=1')

        # first, determine my user name on Facebook (full name)
        # this is needed for filtering wall posts to only include those
        # posted by me (the current fbcmd user)

        fbcmd_whoami_text = self.texthandler(commands.getoutput('fbcmd whoami'))
        matches = re.search('^[0-9]+  (.*)', fbcmd_whoami_text, re.DOTALL)
        username = ""
        if matches:
            username = self.texthandler(matches.group(1))
        else:
            self.msg(0,self.texthandler("Unable to determine your Facebook user name"))
            return self.messages;
        
            
        messages_text = self.texthandler(commands.getoutput('fbcmd fstream =me 120'))

        in_message = False
        msg = Message()

        inlink = False

        line = self.texthandler("")

        for line in messages_text.split('\n'):

            # new messages begin with [number].
            matches = (re.search('^\[[0-9]+\].*', line, re.DOTALL) != None)
            matches = matches and (line[0:len(username)+10].find(username) != -1)
        
            if matches:

                if in_message == True:
                    # we need to close and save the old message before beginning a new one
                    msg.content = self.TextToHtml(msg.content)
                    msg.id = self.generate_id(msg.content)
                    self.messages.append( msg )
                    inlink = False
                    pass
                
                # Start a new message
                in_message = True
                
                msg = Message()
                msg.source = "Facebook"
                
                # find date of message
                message_date_match = re.search('%s.*?([0-9]{4,4} .*?:[0-9][0-9]) ([-,\+][0-9]+)  ' % (username),line,re.DOTALL)
                if message_date_match:
                    t = (datetime.datetime.strptime(message_date_match.group(1), '%Y %a %b %d %H:%M') - datetime.timedelta(seconds=int(message_date_match.group(2)))).timetuple()
                    msg.date = calendar.timegm(t)
                    pass
                else:
                    self.msg(0,username)
                    self.msg(0,line)
                    self.msg(3,"Unable to obtain message date and time")
                    pass
                
                # we need to find the start of the actual message
                message_text_match = re.search('.*attach post  (.*)',line,re.DOTALL)
                if message_text_match == None:
                    message_text_match = re.search('.*link post  (.*)',line,re.DOTALL)
                    pass
                if message_text_match == None:
                    message_text_match = re.search('.*photo post  (.*)',line,re.DOTALL)
                    pass
                if message_text_match != None:
                    msg.content =  self.texthandler(message_text_match.group(1))
                    if re.search('http\S+$',message_text_match.group(1),re.DOTALL) != None:
                        inlink = True
                        pass
                    else:
                        inlink = False
                        pass
                else:
                    print "PROBLEM:"
                    print line.encode("iso-8859-1")
                    pass
                pass

            elif in_message:
                hit_likes_or_comments = (line.find(':likes') != -1) or (line.find(':comment') != -1)
                hit_link = (line.find(':link') != -1)
                hit_name = (line.find(':name') != -1)
                hit_caption = (line.find(':caption') != -1)
                hit_desc = (line.find(':desc') != -1)
                hit_blankline = (re.search('^$',line) != None)
                if hit_likes_or_comments or hit_blankline:
                    # we have finished the message content. Close it.
                    in_message = False
                    msg.content = self.TextToHtml(msg.content)
                    msg.id = self.generate_id(msg.content)
                    self.messages.append( msg )
                    inlink = False
                    pass
                elif hit_name or hit_link or hit_caption or hit_desc:
                    message_text_match = re.search('.*?:(link|caption|name|desc).*?(\S.*)',line, re.DOTALL)
                    msg.repost = 1
                    if msg.content.find("Shared from Facebook:") == -1:
                        msg.content = "Shared from Facebook: " + msg.content
                        pass
                    if message_text_match != None:
                        msg.content = msg.content + "\n\n" + message_text_match.group(2)
                        pass
                    pass
                else:
                    # we are still in the last message - keep doing things
                    message_text_match = re.search('.*?(\S.*)',line, re.DOTALL)
                    spacer = ""

                    if message_text_match != None:
                        if inlink:
                            spacer = ""
                            
                            # see if we continue to be in a link at the end of this line
                            if re.search('.*\s.*', message_text_match.group(1),re.DOTALL) != None:
                                # this line contains whitespace - the URL must end in here
                                inlink = False
                            else:
                                # the url continues unbroken by whitespace
                                inlink = True
                                pass
                            pass

                        else:
                            spacer = " "

                            # see if a link begins in this line
                            if re.search('http\S+$', message_text_match.group(1),re.DOTALL) != None:
                                inlink = True
                            else:
                                inlink = False
                                spacer = " "
                                pass
                            
                            pass
                        

                        msg.content = msg.content + spacer + message_text_match.group(1)
                        pass
                    
                pass
            pass

        # handle images - they don't show up in the fstream
        messages_text = commands.getoutput('fbcmd opics =me')

        in_message = False
        msg = Message()

        photo_pid_column = -1
        text_column = -1

        first_line_pattern = re.compile('^%s\s+([0-9]+_[0-9]+)\s+([0-9]{4} [A-Za-z]{3} [A-Za-z]{3} [0-9]{2} [0-9]{2}:[0-9]{2}) ([-,\+][0-9]+)(\s.*)' % (username))
        message_line_pattern = re.compile('^.*\s+([0-9]+_[0-9]+)\s+([0-9]{4} [A-Za-z]{3} [A-Za-z]{3} [0-9]{2} [0-9]{2}:[0-9]{2}) ([-,\+][0-9]+)(\s.*)')

        for line in messages_text.split('\n'):

            line = str(line)

            if line.find("NAME") != 1 and line.find("PID") != -1 and line.find("CAPTION") != -1:
                continue

            # new messages begin with a PID. To determine the column containing
            # the PID, we need to do some math.
        
            # Stephen Sekula  100000196682628_1073741900  2014 Sun May 11 14:23  Tracking down bug
            first_line_pattern_match = first_line_pattern.search(line)
            if first_line_pattern_match != None and photo_pid_column == -1:
                # we found the key line of the output - find the column where the PID starts
                pid = first_line_pattern_match.group(1)
                photo_pid_column = line.find(pid)
                pass

            pid_pattern = re.search('^.*?  ([0-9]+_[0-9]+)\s.*', line, re.DOTALL)
            pid_match = re.search("[0-9]", line[photo_pid_column],re.DOTALL)
            if pid_match:
                pid = pid_pattern.group(1)
                if not in_message:
                    # we found the first line of a photo message.
                    msg = Message()
                    msg.source = "Facebook"
                    
                    # find date of message

                    message_date_match = message_line_pattern.search(line)
                    datetext = ""
                    dateoffset = ""
                    if message_date_match:
                        datetext = message_date_match.group(2)
                        dateoffset = message_date_match.group(3)

                        t = (datetime.datetime.strptime(datetext, '%Y %a %b %d %H:%M') - datetime.timedelta(seconds=int(dateoffset))).timetuple()
                        msg.date = calendar.timegm(t)
                        pass
                    else:
                        self.msg(3,"Unable to determine date and time of photo.")
                        pass

                    # we need to find the start of the actual message
                    text_column = photo_pid_column+len(pid)+2+len(datetext)+1+len(dateoffset)
                    msg.content = str(msg.content) + line[text_column:].lstrip()
                    
                    in_message = True
                    pass
                else:
                    # we found the start of the next message. close the last one
                    msg.content = self.TextToHtml(msg.content)
                    msg.id = self.generate_id(msg.content)
                    
                    # check if the message has any content before saving
                    if re.search(".*[A-Za-z0-9].*",msg.content,re.DOTALL) != None:
                        self.messages.append(msg)
                        pass

                    msg = Message()
                    msg.source = "Facebook"

                    # Find date of message
                    message_date_match = message_line_pattern.search(line)

                    datetext = ""
                    dateoffset = ""
                    if message_date_match:
                        datetext = message_date_match.group(2)
                        dateoffset = message_date_match.group(3)

                        t = (datetime.datetime.strptime(datetext, '%Y %a %b %d %H:%M') - datetime.timedelta(seconds=int(dateoffset))).timetuple()
                        msg.date = calendar.timegm(t)
                        pass
                    else:
                        self.msg(3,"Unable to determine date and time of photo.")
                        pass

                    msg.content = str(msg.content) + line[text_column:].lstrip()
                    in_message = True
                    pass
                pass
            else:
                # we are still in the last message - keep doing things

                msg.content = str(msg.content + " " + line[text_column:].lstrip())

                pass
            pass

        self.messages = sorted(self.messages, key=lambda msg: msg.date, reverse=False)

        if self.debug:
            print "********************** Facebook Handler **********************\n"
            print "Here are the messages I gathered from the Facebook server:\n"
            for message in self.messages:
                print message.Printable()
                pass
            print "**************************************************************\n"

        return self.messages
    

    def write(self, messages):
        if not self.active:
            self.msg(0,"Facebook handler not active; no messages will be posted")
            return

        write_count = 0

        for message in messages:

            self.msg(0,"writing to Facebook")
            self.msg(0,"Share level is: %s" % (self.sharelevel))

            
            do_write = False
            if self.sharelevel == "All":
                do_write = True
            elif self.sharelevel.find("Public") != -1 and message.public == 1:
                do_write = True
                pass
            else:
                self.msg(0,message.content)
                self.msg(0,"Unable to share message based on sharelevel settings.")
                do_write = False
                pass

            if not do_write:
                continue
            
            if len(message.attachments) > 0:
                if self.debug:
                    self.msg(0,"   Posting a photo.")
                    pass

                for attachment in message.attachments:
                    command = "fbcmd ADDPIC %s \"%s\" \"%s\"" % (attachment, self.album, message.content)
                    if self.debug:
                        self.msg(0, "   " + command)
                        pass
                    results = commands.getoutput(command)
                    pass
                pass
            else:
                command = "fbcmd STATUS \"%s\"" % (message.content)
                if self.debug:
                    self.msg(0, "   " + command)
                    pass
                results = commands.getoutput(command)
                pass

            write_count += 1
            pass

        self.msg(0,"Wrote %d messages" % write_count)
        return

