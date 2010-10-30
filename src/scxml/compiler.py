'''
This file is part of pyscxml.

    pyscxml is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    pyscxml is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with pyscxml.  If not, see <http://www.gnu.org/licenses/>.
    
    @author Johan Roxendal
    @contact: johan@roxendal.com
    
'''


from node import *
from urllib2 import urlopen
import sys, re
from xml.etree import ElementTree, ElementInclude
from functools import partial
from xml.sax.saxutils import unescape
import logger

tagsForTraversal = ["scxml", "state", "parallel", "history", "final", "transition", "invoke", "onentry", "onexit", "data", "datamodel"]


class Compiler(object):
    '''The class responsible for compiling the statemachine'''
    def __init__(self):
        self.doc = SCXMLDocument()
        self.logger = logger.initLogger("scxml.Compiler, id: " + str(id(self)))
    
    def parseAttr(self, elem, attr, is_list=False):
        if not elem.get(attr, elem.get(attr + "expr")):
            return
        else:
            output = elem.get(attr) if elem.get(attr) else self.getExprValue(elem.get(attr + "expr")) 
            return output if not is_list else output.split(" ")
        
    
    def getExecContent(self, parent):
        '''
        @param parent: usually an xml Element containing executable children
        elements, but can also be any iterator of executable elements. 
        @return: a function corresponding to the executable content. 
        '''
        fList = []
        for node in parent:
            
            if node.tag == "log":
                fList.append(getLogFunction(node.get("label"),  partial(self.getExprValue, node.get("expr"))))
            elif node.tag == "raise": 
                eventName = node.get("event").split(".")
                fList.append(partial(self.interpreter.raiseFunction, eventName))
            elif node.tag == "send":
                fList.append(partial(self.parseSend, node))
            elif node.tag == "cancel":
                fList.append(partial(self.interpreter.cancel, node.get("sendid")))
            elif node.tag == "assign":
                expression = node.get("expr") if node.get("expr") else node.text
                # ugly scoping hack
                def utilF(loc=node.get("location"), expr=expression):
                    self.doc.datamodel[loc] = self.getExprValue(expr)
                fList.append(utilF)
            elif node.tag == "script":
                fList.append(self.getExprFunction(node.text))
            elif node.tag == "if":
                fList.append(partial(self.parseIf, node))
            else:
                sys.exit("%s is either an invalid child of %s or it's not yet implemented" % (node.tag, node.parent.tag))
        
        # return a function that executes all the executable content of the node.
        def f():
            for func in fList:
                func()
        return f
    
    def parseIf(self, node):
        def gen_prefixExec(itr):
            for elem in itr:
                if elem.tag not in ["elseif", "else"]:
                    yield elem
                else:
                    break

        def gen_ifblock(ifnode):
            yield (ifnode, gen_prefixExec(ifnode))
            for elem in (x for x in ifnode if x.tag == "elseif" or x.tag == "else"):
                elemIndex = list(ifnode).index(elem)
                yield (elem, gen_prefixExec(ifnode[elemIndex+1:]))
        
        for ifNode, execList in gen_ifblock(node):
            if ifNode.tag == "else":
                self.getExecContent(execList)()
            elif self.getExprValue(ifNode.get("cond")):
                self.getExecContent(execList)()
                break
    
    def parseData(self, child):
        '''
        Given a parent node, returns a data object corresponding to 
        its param child nodes or namelist attribute.
        '''
        output = {}
        for p in child.findall("param"):
            expr = p.get("expr", p.get("name"))
            
            output[p.get("name")] = self.getExprValue(expr)
                
        
        if child.get("namelist"):
            for name in child.get("namelist").split(" "):
                output[name] = self.getExprValue(name)
        
        return output
    
    def parseSend(self, sendNode):
        type = sendNode.get("type") if sendNode.get("type") else "scxml"
        delay = int(self.parseAttr(sendNode, "delay")) if self.parseAttr(sendNode, "delay") else 0
        
        event = self.parseAttr(sendNode, "event").split(".")
        
        target = self.parseAttr(sendNode, "target")
        
        if not target:
            self.interpreter.send(event, sendNode.get("id"), delay)
        elif target[0] == "#":
            target = target[1:]
            
            if(type == "scxml"):
                if(target == "_parent"):
                    self.interpreter.send(event, sendNode.get("id"), delay, self.parseData(sendNode), self.interpreter.invokeId, toQueue=self.doc.datamodel["_parent"])
                else:
                    self.doc.datamodel[target].send(event, sendNode.get("id"), delay, self.parseData(sendNode))
            # this is where to add parsing for more send types. 
#            elif(type == "basichttp"):
    
    
    def parseXML(self, xmlStr, interpreterRef):
        self.interpreter = interpreterRef
        xmlStr = removeDefaultNamespace(xmlStr)
        tree = ElementTree.fromstring(xmlStr)
        ElementInclude.include(tree)
        preprocess(tree)
        
        for n, parent, node in iter_elems(tree):
            if parent != None and parent.get("id"):
                parentState = self.doc.getState(parent.get("id"))
                
            
            if node.tag == "scxml":
                s = State(node.get("id"), None, n)
                s.initial = self.parseInitial(node)
                    
                if node.find("script") != None:
                    self.getExprFunction(node.find("script").text)()
                self.doc.rootState = s    
                
            elif node.tag == "state":
                s = State(node.get("id"), parentState, n)
                s.initial = self.parseInitial(node)
                
                self.doc.addNode(s)
                parentState.addChild(s)
                
            elif node.tag == "parallel":
                s = Parallel(node.get("id"), parentState, n)
                self.doc.addNode(s)
                parentState.addChild(s)
                
            elif node.tag == "final":
                s = Final(node.get("id"), parentState, n)
                self.doc.addNode(s)
                
                if node.find("donedata") != None:
                    s.donedata = partial(self.parseData, node.find("donedata"))
                else:
                    s.donedata = lambda:{}
                
                parentState.addFinal(s)
                
            elif node.tag == "history":
                h = History(node.get("id"), parentState, node.get("type"), n)
                self.doc.addNode(h)
                parentState.addHistory(h)
                
                
            elif node.tag == "transition":
                t = Transition(parentState)
                if node.get("target"):
                    t.target = node.get("target").split(" ")
                if node.get("event"):
                    t.event = map(lambda x: re.sub(r"(.*)\.\*$", r"\1", x).split("."), node.get("event").split(" "))
                if node.get("cond"):
                    t.cond = partial(self.getExprValue, node.get("cond"))    
                
                t.exe = self.getExecContent(node)
                    
                parentState.addTransition(t)
    
            elif node.tag == "invoke":
                
                inv = self.parseInvoke(node)
                
                parentState.addInvoke(inv)
                           
            elif node.tag == "onentry":
                s = Onentry()
                s.exe = self.getExecContent(node)
                parentState.addOnentry(s)
            
            elif node.tag == "onexit":
                s = Onexit()
                s.exe = self.getExecContent(node)
                parentState.addOnexit(s)
            elif node.tag == "data":
                self.doc.datamodel[node.get("id")] = self.getExprValue(node.get("expr"))
                
                
                
    
        return self.doc

    def getExprFunction(self, expr):
        expr = normalizeExpr(expr)
        def f():
            exec expr in self.doc.datamodel
        return f
    
    def getExprValue(self, expr):
        """These expression are always one-line, so their value is evaluated and returned."""
        if not expr: 
            return None
        expr = unescape(expr)
        return eval(expr, self.doc.datamodel)

    def parseInvoke(self, node):
        if node.get("type") == "scxml": # here's where we add more invoke types. 
                     
            inv = InvokeSCXML(node.get("id"))
            if node.get("src"):
                inv.content = urlopen(node.get("src")).read()
            elif node.find("content") != None:
                inv.content = ElementTree.tostring(node.find("content/scxml"))
            
            inv.autoforward = bool(node.get("autoforward"))
        
        
        inv.type = node.get("type")   
        
        if node.find("finalize") != None and len(node.find("finalize")) > 0:
            inv.finalize = self.getExecContent(node.find("finalize"))
        elif node.find("finalize") != None and node.find("param") != None:
            paramList = node.findall("param")
            def f():
                for param in (p for p in paramList if not p.get("expr")): # get all param nodes without the expr attr
                    if self.doc.datamodel["_event"].data.has_key(param.get("name")):
                        self.doc.datamodel[param.get("name")] = self.doc.datamodel["_event"].data[param.get("name")]
            inv.finalize = f
        return inv

    def parseInitial(self, node):
        if node.get("initial"):
            return Initial(node.get("initial").split(" "))
        elif node.find("initial") is not None:
            transitionNode = node.find("initial")[0]
            assert transitionNode.get("target")
            initial = Initial(transitionNode.get("target").split(" "))
            initial.exe = self.getExecContent(transitionNode)
            return initial
        else: # has neither initial tag or attribute, so we'll make the first valid state a target instead.
            childNodes = filter(lambda x: x.tag in ["state", "parallel", "final"], list(node)) 
            if childNodes:
                return Initial([childNodes[0].get("id")])
            return None # leaf nodes have no initial 
    

    
def getLogFunction(label, toPrint):
    if not label: label = "Log"
    def f():
        print "%s: %s" % (label, toPrint())
    return f
    

def preprocess(tree):
    tree.set("id", "__main__")
    
    for n, parent, node in iter_elems(tree):
        if node.tag in ["state", "parallel", "final", "invoke", "history"] and not node.get("id"):
            id = parent.get("id") + "_%s_child_%s" % (node.tag, n)
            node.set('id',id)
            

def normalizeExpr(expr):
    # TODO: what happens if we have python strings in our script blocks with &gt; ?
    code = unescape(expr).strip("\n")
    
    firstLine = code.split("\n")[0]
    # how many whitespace chars in first line?
    indent_len = len(firstLine) - len(firstLine.lstrip())
    # indent left by indent_len chars
    code = "\n".join(map(lambda x:x[indent_len:], code.split("\n")))
    
    return code
    

def removeDefaultNamespace(xmlStr):
    return re.sub(r" xmlns=['\"].+?['\"]", "", xmlStr)

def iter_elems(tree):
    queue = [(None, tree)]
    n = 0
    while(len(queue) > 0):
        parent, child = queue.pop(0)
        yield (n, parent, child)
        n += 1 
        for elem in child:
            if elem.tag in tagsForTraversal:
                queue.append((child, elem))

    