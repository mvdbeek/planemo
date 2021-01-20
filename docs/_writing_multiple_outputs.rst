.. _multiple-output-files:

Multiple Output Files
===========================================

Tools which create more than one output file are common.  There are several different methods to accommodate this need.  Each one of these has their advantages and weaknesses; careful thought should be employed to determine the best method for a particular tool.

-------------------------------------------
Static Multiple Outputs
-------------------------------------------

Handling cases when tools create a static number of outputs is simple.  Simply include an ``<output>`` tag for each output desired within the tool XML file:

.. code-block:: xml

    <tool id="example_tool" name="Multiple output" description="example">
        <command>example_tool.sh '$input1' $tool_option1 '$output1' '$output2'</command>
        <inputs>
            ...
        </inputs>
        ...
        <outputs>
            <data format="interval" name="output1" metadata_source="input1" />
            <data format="pdf" name="output2" />
        </outputs>
    </tool>
  
---------------------------------------------------------
Static Outputs Determinable from Inputs 
---------------------------------------------------------

In cases when the number of output files varies, but can be determined based upon a user's parameter selection, the filter tag can be used.  The text contents of the ``<filter>`` tag are ``eval``ed and if the expression is ``True`` a dataset will be created as normal.  If the expression is ``False``, the output dataset will not be created; instead a ``NoneDataset`` object will be created and made available. When used on the command line the text ``None`` will appear instead of a file path. The local namespace of the filter has been populated with the tool parameters.

.. code-block:: xml

    <tool id="example_tool" name="Multiple output" description="example">
        <command>example_tool.sh '$input1' $tool_option1 '$output1' '$output2'</command>
        <inputs>
           ...
           <param name="tool_option1" type="select" label="Type of output">
               <option value="1">Single File</option>
               <option value="2">Two Files</option>
           </param>
           <conditional name="condition1">
               <param name="tool_option2" type="select" label="Conditional output">
                   <option value="yes">Yes</option>
                   <option value="no">No</option>
               </param>
               ...
           </condition>
           ...
        </inputs>
        ...
        <outputs>
            <data format="interval" name="output1" metadata_source="input1" />
            <data format="pdf" name="output2" >
                <filter>tool_option1 == "2"</filter>
            </data>
            <data format="txt" name="output3" >
                <filter>condition1['tool_option2'] == "yes"</filter>
            </data>
        </outputs>
    </tool>


The command line generated when ``tool_option1`` is set to ``Single File`` is:


::

    example_tool.sh input1_FILE_PATH 1 output1_FILE_PATH None



The command line generated when ``tool_option1`` is set to ``Two Files`` is:

::

    example_tool.sh input1_FILE_PATH 2 output1_FILE_PATH output2_FILE_PATH

The datatype of an output can be determined by conditional parameter settings as in `tools/filter/pasteWrapper.xml <https://github.com/galaxyproject/galaxy/blob/dev/tools/filters/cutWrapper.xml>`__

.. code-block:: xml

    <outputs>
        <data format="input" name="out_file1" metadata_source="input1">
            <change_format>
                <when input_dataset="input1" attribute="ext" value="bed" format="interval"/>
            </change_format>
        </data>
    </outputs>


---------------------------------------------------------
Single HTML Output
---------------------------------------------------------

There are times when a single history item is desired, but this history item is composed of multiple files which are only useful when considered together. This is done by having a single (``primary``) output and storing additional files in a directory (single-level) associated with the primary dataset.

A common usage of this strategy is to have the primary dataset be an HTML file and then store additional content (reports, pdfs, images, etc) in the dataset extra files directory. The content of this directory can be referenced using relative links within the primary (HTML) file, clicking on the eye icon to view the dataset will display the HTML page.

If you want to wrap or create a tool that generates an HTML history item that shows the user links to a number of related output objects (files, images..), you need to know where to write the objects and how to reference them when your tool generates HTML which gets written to the HTML file. Galaxy will not write that HTML for you at present.

The `fastqc wrapper <https://github.com/galaxyproject/tools-devteam/blob/master/tools/fastqc/rgFastQC.xml>`__ is an existing tool example where the Java application generates HTML and image outputs but these need to be massaged to make them Galaxy friendly. In other cases, the application or your wrapper must take care of all the fiddly detailed work of writing valid html to display to the user. In either situation, the ``html`` datatype offers a flexible way to display very complex collections of related outputs inside a single history item or to present a complex html page generated by an application. There are some things you need to take care of for this to work:

The following example demonstrates declaring an output of type ``html``.

.. code-block:: xml

    <outputs>
        <data format="html" name="html_file" label="myToolOutput_${tool_name}.html">
    </outputs>

The application or script must be set up to write all the output files and/or images to a new special subdirectory passed as a command line parameter from Galaxy every time the tool is run. The paths for images and other files will end up looking something like ``$GALAXY_ROOT/database/files/000/dataset_56/img1.jpg`` when you prepend the Galaxy provided path to the filenames you want to use. The command line must pass that path to your script and it is specified using the ``extra_files_path`` property of the HTML file output.

For example:


.. code-block:: xml


    <command>myscript.pl '$input1' '$html_file' '$html_file.extra_files_path' </command>


The application must create and write valid html to setup the page ``$html_file`` seen by the user when they view (eye icon) the file. It must create and write that new file at the path passed by Galaxy as the ``$html_file`` command line parameter. All application outputs that will be included as links in that html code should be placed in the specific output directory ``$html_file.extra_files_path`` passed on the command line. The external application is responsible for creating that directory before writing images and files into it. When generating the html, The files written by the application to ``$html_file.extra_files_path`` are referenced in links directly by their name, without any other path decoration - eg:


.. code-block:: xml

    <a href="file1.xls">Some special output</a>
    <br/>
    <img src="image1.jpg" >

The (now unmaintained) Galaxy Tool Factory includes code to gather all output files and create a page with links and clickable PDF thumbnail images which may be useful as a starting point (e.g. see `rgToolFactory2.py <https://github.com/galaxyproject/tools-iuc/blob/master/tools/tool_factory_2/rgToolFactory2.py#L741>`__.

``galaxy.datatypes.text.Html`` (the ``html`` datatype) is a subclass of composite datasets so new subclasses of composite can be used to implement even more specific structured outputs but this requires adding the new definition to Galaxy - whereas Html files require no extension of the core framework. For more information visit `Composite Datatypes <https://docs.galaxyproject.org/en/master/dev/data_types.html#composite-datatypes>`__. 


---------------------------------------------------------
Dynamic Numbers of Outputs
---------------------------------------------------------

This section discusses the case where the number of output datasets cannot be determined until the tool run is complete. If the outputs can be broken into groups or collections of similar/homogenous datasets - this is possibly a case for using dataset collections. If instead the outputs should be treated individually and Galaxy's concept of dataset collections doesn't map cleanly to the outputs - Galaxy can "discover" individual output datasets dynamically after the job is complete.

Collections
---------------------------------------------------------

See the Planemo documentation on `creating collections <http://planemo.readthedocs.io/en/latest/writing_advanced.html#creating-collections>`__ for more details on this topic.

A blog post on generating dataset collections from tools can be found
`here <https://web.science.mq.edu.au/~cassidy/2015/10/21/galaxy-tool-generating-datasets/>`__.

Individual Datasets
---------------------------------------------------------

There are times when the number of output datasets varies entirely based upon the content of an input dataset and the user needs to see all of these outputs as new individual history items rather than as a collection of datasets or a group of related files linked in a single new HTML page in the history. Tools can optionally describe how to "discover" an arbitrary number of files that will be added after the job's completion to the user's history as new datasets. Whenever possible, one of the above strategies should be used instead since these discovered datasets cannot be used with workflows and require the user to refresh their history before they are shown.

Discovering datasets (arbitrarily) requires a fixed "parent" output dataset to key on - this dataset will act as the reference for our additional datasets. Sometimes the parent dataset that should be used makes sense from context but in instances where one does not readily make sense tool authors can just create an arbitrary text output (like a report of the dataset generation).

Each discovered dataset requires a unique "designation" (used to describe functional tests, the default output name, etc...) and should be located in the job's working direcotry or a sub-directory thereof. Regular expressions are used to describe how to discover the datasets and (though not required) a unique such pattern should be specified for each homogeneous group of such files.

~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Consider a tool that creates a bunch of text files or bam files and writes them (with extension that matches the Galaxy datatype - e.g. ``txt`` or ``bam`` to the ``split`` sub-directory of the working directory. Such outputs can be discovered by adding the following block of XML to your tool description:

.. code-block:: xml

    <outputs>
        <data name="report" format="txt">
            <discover_datasets pattern="__designation_and_ext__" directory="split" visible="true" />
        </data>
    </outputs>

So for instance, if the tool creates 4 files (in addition to the report) such as ``split/samp1.bam``, ``split/samp2.bam``, ``split/samp3.bam``, and ``split/samp4.bam`` - then 4 discovered datasets will be created of type ``bam`` with designations of ``samp1``, ``samp2``, ``samp3``, and ``samp4``.

If the tool doesn't create the files in ``split`` with extensions or does but with extensions that do not match Galaxy's datatypes - a slightly different pattern can be used and the extension/format can be statically specified (here either ``ext`` or ``format`` may be used as the attribute name):

.. code-block:: xml

    <outputs>
        <data name="report" format="txt">
            <discover_datasets pattern="__designation__" format="tabular" directory="tables" visible="true" />
        </data>
    </outputs>

So in this example, if the tool creates 3 tabular files such as ``tables/part1.tsv``, ``tables/part2.tsv``, and ``tables/part3.tsv`` - then 3 discovered datasets will be created of type ``tabular`` with designations of ``part1.tsv``, ``part2.tsv``, and ``part3.tsv``.

It may not be desirable for the extension/format (``.tsv``) to appear in the ``designation`` this way. These patterns ``__designation__`` and  ``__designation_and_ext__`` are replaced with regular expressions that capture metadata from the file name using named groups. A tool author can explicitly define these regular expressions instead of using these shortcuts - for instance ``__designation__`` is just ``(?P<designation>.*)`` and ``__designation_and_ext__`` is ``(?P<designation>.*)\.(?P<ext>[^\._]+)?``. So the above example can be modified as:

.. code-block:: xml

    <outputs>
        <data name="report" format="txt">
            <discover_datasets pattern="(?P&lt;designation&gt;.+)\.tsv" format="tabular" directory="tables" visible="true" />
        </data>
    </outputs>

As a result - three datasets are still be captured - but this time with designations of ``part1``, ``part2``, and ``part3``.

Notice here the ``<`` and ``>`` in the tool pattern had to be replaced with ``\&lt;`` and ``&gt;`` to be properly embedded in XML (this is very ugly - apologies).

The metadata elements that can be captured via regular expression named groups this way include ``ext``, ``designation``, ``name``, ``dbkey``, and ``visible``. Each pattern must declare at least either a ``designation`` or a ``name`` - the other metadata parts ``ext``, ``dbkey``, and ``visible`` are all optional and may also be declared explicitly in via attributes on the ``discover_datasets`` element (as shown in the above examples).

For tools which do not define a ``profile`` version or define one before 16.04, if no ``discover_datasets`` element is nested with a tool output - Galaxy will still look for datasets using the named pattern ``__default__`` which expands to ``primary_DATASET_ID_(?P<designation>[^_]+)_(?P<visible>[^_]+)_(?P<ext>[^_]+)(_(?P<dbkey>[^_]+))?``. Many tools use this mechanism as it traditionally was the only way to discover datasets and has the nice advantage of not requiring an explicit declaration and encoding everything (including the output to map to) right in the name of the file itself.

For instance consider the following output declaration:

.. code-block:: xml

    <outputs>
        <data format="interval" name="output1" metadata_source="input1" />
    </outputs>


If ``$output1.id`` (accessible in the tool ``command`` block) is ``546`` and the tool (likely a wrapper) produces the files ``primary_546_output2_visible_bed`` and ``primary_546_output3_visible_pdf`` in the job's working directory - then after execution is complete these two additional datasets (a ``bed`` file and a ``pdf`` file) are added to the user's history.

Newer tool profile versions disable this and require the tool author to be more explicit about what files are discovered.

~~~~~~~~~~~~~~~~~~~~~~~~~~~~
More information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~


* Example tools which demonstrate discovered datasets:

  * `multi_output.xml <https://github.com/galaxyproject/galaxy/blob/dev/test/functional/tools/multi_output.xml>`__
  * `multi_output_assign_primary.xml <https://github.com/galaxyproject/galaxy/blob/dev/test/functional/tools/multi_output_assign_primary.xml>`__
  * `multi_output_configured.xml <https://github.com/galaxyproject/galaxy/blob/dev/test/functional/tools/multi_output_configured.xml>`__

* `Original pull request for discovered dataset enhancements with implementation details <http://bit.ly/gxdiscovereddatasetpr>`__
* `Implementation of output collection code in galaxy <https://github.com/galaxyproject/galaxy/blob/master/lib/galaxy/tools/parameters/output_collect.py>`__

~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Legacy information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~


In the past, it would be necessary to set the attribute ``force_history_refresh`` to ``True`` to force the user's history to fully refresh after the tool run has completed. This functionality is now broken and ``force_history_refresh`` is ignored by Galaxy. Users now **MUST** manually refresh their history to see these files. A Trello card used to track the progress on fixing this and eliminating the need to refresh histories in this manner can be found [[https://trello.com/c/f5Ddv4CS/1993-history-api-determine-history-state-running-from-join-on-running-jobs|here]].

Discovered datasets are available via post job hooks (a deprecated feature) by using the designation - e.g. ``__collected_datasets__['primary'][designation]``.

In the past these datasets were typically written to ``$__new_file_path__`` instead of the working directory. This is not very scalable and ``$__new_file_path__`` should generally not be used. If you set the option ``collect_outputs_from`` in ``galaxy.ini`` ensure ``job_working_directory`` is listed as an option (if not the only option).
