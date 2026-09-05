package com.example.minicpm_v_demo

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.view.MotionEvent
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.appbar.AppBarLayout
import com.google.android.material.textfield.TextInputEditText
import com.example.minicpm_v_demo.harness.HarnessChatRequest
import com.example.minicpm_v_demo.harness.HarnessFacade
import com.example.minicpm_v_demo.harness.character.CharacterCard
import com.example.minicpm_v_demo.harness.rag.AndroidRagOrchestrator
import com.example.minicpm_v_demo.harness.rag.CompiledAndroidPrompt
import com.example.minicpm_v_demo.harness.rag.RagMode
import com.example.minicpm_v_demo.harness.rag.RagSource
import com.example.minicpm_v_demo.harness.data.HarnessDataPaths
import com.example.minicpm_v_demo.harness.session.ChatSession
import com.example.minicpm_v_demo.harness.session.ChatSessionStore
import com.example.minicpm_v_demo.harness.session.ChatTurn
import com.example.minicpm_v_demo.harness.session.MemoryStore
import io.noties.markwon.Markwon
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream

class MainActivity : AppCompatActivity() {

    private lateinit var recyclerChat: RecyclerView
    private lateinit var chatAdapter: ChatAdapter
    private lateinit var etInput: TextInputEditText
    private lateinit var btnSend: ImageButton
    private lateinit var btnImage: ImageButton
    private lateinit var btnCharacter: ImageButton
    private lateinit var btnRagMode: ImageButton
    private lateinit var btnClearChat: ImageButton
    private lateinit var btnModelManager: ImageButton
    private lateinit var btnImageSlice: ImageButton
    private lateinit var cardInputBar: View
    private lateinit var appBarLayout: AppBarLayout
    private lateinit var tvTitle: TextView

    private lateinit var harness: HarnessFacade
    private lateinit var sessionStore: ChatSessionStore
    private lateinit var memoryStore: MemoryStore
    private var ragOrchestrator: AndroidRagOrchestrator? = null
    private var currentSession: ChatSession? = null
    private var currentRagMode: RagMode = RagMode.OFF
    private var generationJob: Job? = null
    private var isModelReady = false
    private var isImagePrefilled = false
    private var isProcessingVideo = false
    private var hasAutoLoaded = false
    private var loadedModelId: String? = null
    private var messageIdCounter = 1L
    private val messages = mutableListOf<ChatMessage>()
    private var createdWithLocale: String? = null
    private var isLocaleRestart = false
    private var currentCharacterId = DEFAULT_CHARACTER_ID
    private var currentStoryCutoff: String? = DEFAULT_STORY_CUTOFF

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createdWithLocale = LocaleManager.currentLanguage(this).tag
        harness = HarnessFacade.getInstance(applicationContext)
        val harnessPaths = HarnessDataPaths.from(applicationContext)
        harnessPaths.ensureRuntimeDirs()
        sessionStore = ChatSessionStore(harnessPaths)
        memoryStore = MemoryStore(harnessPaths)
        currentSession = sessionStore.loadRecentSession()
        currentSession?.characterId?.takeIf { it.isNotBlank() }?.let { currentCharacterId = it }
        currentStoryCutoff = currentSession?.storyCutoff ?: DEFAULT_STORY_CUTOFF
        ragOrchestrator = runCatching { AndroidRagOrchestrator.fromContext(applicationContext) }
            .onFailure { Log.e(TAG, "Failed to initialize Android RAG orchestrator", it) }
            .getOrNull()

        // If the selected model is a TTS model, redirect to TtsActivity immediately.
        // The chat interface is only meaningful for LLM/VLM models.
        if (shouldRedirectToTts()) {
            startActivity(Intent(this, TtsActivity::class.java))
            finish()
            return
        }

        setContentView(R.layout.activity_main)

        // Edge-to-edge: pad the root content for status/nav bars and the IME
        // so the bottom input bar follows the soft keyboard up. Without this,
        // targetSdk=35+ draws content behind the IME and the input bar gets
        // covered.
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val rootContent = findViewById<View>(android.R.id.content)
        ViewCompat.setOnApplyWindowInsetsListener(rootContent) { v, insets ->
            val sysBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            v.updatePadding(
                left = sysBars.left,
                top = sysBars.top,
                right = sysBars.right,
                bottom = maxOf(sysBars.bottom, ime.bottom)
            )
            insets
        }

        harness.migrateLegacyLayoutIfNeeded()

        initViews()
        setupRecyclerView()
        setupClickListeners()
        updateRagModeButton()
        updateCharacterButton()
        observeEngineState()
    }

    private fun initViews() {
        recyclerChat = findViewById(R.id.recycler_chat)
        etInput = findViewById(R.id.et_input)
        btnSend = findViewById(R.id.btn_send)
        btnImage = findViewById(R.id.btn_image)
        btnCharacter = findViewById(R.id.btn_character)
        btnRagMode = findViewById(R.id.btn_rag_mode)
        btnClearChat = findViewById(R.id.btn_clear_chat)
        btnModelManager = findViewById(R.id.btn_model_manager)
        btnImageSlice = findViewById(R.id.btn_image_slice)
        cardInputBar = findViewById(R.id.card_input_bar)
        appBarLayout = findViewById(R.id.appBarLayout)
        tvTitle = findViewById(R.id.tv_title)
    }

    private fun setupRecyclerView() {
        chatAdapter = ChatAdapter(Markwon.create(this))
        chatAdapter.setOnStopClick {
            harness.cancelGeneration()
        }
        chatAdapter.setOnSourcesClick { message ->
            showSourcesDialog(message.sources)
        }
        chatAdapter.setOnPromptClick { message ->
            showPromptDialog(message.debugPrompt.orEmpty())
        }
        chatAdapter.setOnSuggestionClick { suggestion ->
            if (isModelReady && !isProcessingVideo) {
                etInput.setText(suggestion)
                handleUserInput()
            } else if (!isModelReady) {
                Toast.makeText(this, R.string.toast_load_model_first, Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, R.string.toast_wait_video, Toast.LENGTH_SHORT).show()
            }
        }

        recyclerChat.layoutManager = LinearLayoutManager(this)
        recyclerChat.adapter = chatAdapter

        cardInputBar.viewTreeObserver.addOnGlobalLayoutListener {
            recyclerChat.setPadding(
                recyclerChat.paddingLeft,
                recyclerChat.paddingTop,
                recyclerChat.paddingRight,
                cardInputBar.height
            )
        }

        val selectedModel = harness.getSelectedModel()
        messages.add(ChatMessage.WelcomeCard(isTextOnly = selectedModel.isTextOnly))
        restoreRecentSessionMessages()
        chatAdapter.submitList(messages.toList())
    }

    private fun restoreRecentSessionMessages() {
        val restoredTurns = currentSession?.turns.orEmpty().takeLast(20)
        if (restoredTurns.isEmpty()) return
        var nextId = messageIdCounter
        restoredTurns.forEach { turn ->
            messages.add(
                ChatMessage.UserMessage(
                    id = nextId++,
                    text = turn.userText,
                ),
            )
            messages.add(
                ChatMessage.AiMessage(
                    id = nextId++,
                    text = turn.assistantText,
                    isGenerating = false,
                    ragMode = runCatching { RagMode.valueOf(turn.ragMode) }.getOrNull(),
                    sources = turn.sources,
                    debugPrompt = turn.renderedPrompt,
                ),
            )
        }
        messageIdCounter = nextId
    }

    private fun setupClickListeners() {
        // Pick image OR video.  iOS demo's HXPhotoPicker exposes both
        // photo and video in a single picker; on Android we ask SAF
        // for either MIME, so the user gets the same "pick anything
        // viewable" affordance with no extra "video" button.  Video is
        // only fed to the model if the loaded model is V-4.6 (gated in
        // [handleSelectedMedia] / [LlamaEngine.isVideoUnderstandingSupported]).
        btnImage.setOnClickListener { getMedia.launch(arrayOf("image/*", "video/*")) }
        btnSend.setOnClickListener { handleUserInput() }
        btnCharacter.setOnClickListener { showCharacterDialog() }
        btnRagMode.setOnClickListener { showRagModeDialog() }
        btnClearChat.setOnClickListener { showClearChatDialog() }
        btnModelManager.setOnClickListener {
            startActivity(Intent(this, ModelManagerActivity::class.java))
        }
        btnImageSlice.setOnClickListener { showImageSliceDialog() }

        etInput.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus) {
                collapseAppBar()
                scrollToBottom()
            }
        }
    }

    private fun collapseAppBar() {
        appBarLayout.setExpanded(false, true)
    }

    private fun scrollToBottom() {
        recyclerChat.post {
            val adapterCount = chatAdapter.itemCount
            if (adapterCount == 0) return@post
            val layoutManager = recyclerChat.layoutManager as? LinearLayoutManager ?: return@post
            val lastView = layoutManager.findViewByPosition(adapterCount - 1)
            if (lastView != null) {
                val offset = recyclerChat.height - recyclerChat.paddingBottom - lastView.height
                layoutManager.scrollToPositionWithOffset(adapterCount - 1, offset.coerceAtMost(0))
            } else {
                recyclerChat.scrollToPosition(adapterCount - 1)
            }
        }
    }

    private fun showClearChatDialog() {
        AlertDialog.Builder(this)
            .setTitle(R.string.clear_chat)
            .setMessage(R.string.clear_chat_confirm)
            .setPositiveButton(R.string.confirm) { _, _ ->
                clearChat()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    /**
     * Pops up the slice-cap picker.  The slider drives a live preview of
     * the selected value; only on dialog "confirm" do we persist + push
     * the value to native.  Cancel = no-op.
     *
     * Live update path is cheap (no mmproj reload), but we still gate it
     * behind a confirm step so users don't accidentally regenerate cached
     * embeddings while dragging the knob.
     */
    private fun showImageSliceDialog() {
        val view = layoutInflater.inflate(R.layout.dialog_image_slice, null, false)
        val slider = view.findViewById<com.google.android.material.slider.Slider>(R.id.slider_image_slice)
        val tvValue = view.findViewById<android.widget.TextView>(R.id.tv_image_slice_value)

        val initial = harness.getImageMaxSliceNums()
        slider.value = initial.toFloat()
        tvValue.text = initial.toString()
        slider.addOnChangeListener { _, value, _ -> tvValue.text = value.toInt().toString() }

        AlertDialog.Builder(this)
            .setTitle(R.string.image_slice_dialog_title)
            .setView(view)
            .setPositiveButton(android.R.string.ok) { _, _ ->
                val chosen = slider.value.toInt()
                lifecycleScope.launch {
                    harness.setImageMaxSliceNums(chosen)
                    val msgRes = if (harness.isVisionSupported) {
                        R.string.image_slice_apply_toast
                    } else {
                        R.string.image_slice_pending_toast
                    }
                    Toast.makeText(this@MainActivity, getString(msgRes, chosen), Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun clearChatUI() {
        messages.clear()
        val selectedModel = harness.getSelectedModel()
        messages.add(ChatMessage.WelcomeCard(isTextOnly = selectedModel.isTextOnly))
        messageIdCounter = 1L
        isImagePrefilled = false
        chatAdapter.submitList(messages.toList())
    }

    private fun clearChat() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                harness.clearContext()
                sessionStore.clearRecentSession()
                currentSession = null
                withContext(Dispatchers.Main) {
                    clearChatUI()
                    Toast.makeText(this@MainActivity, R.string.clear_chat_toast, Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error clearing context", e)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, getString(R.string.toast_clear_chat_failed, e.message), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun observeEngineState() {
        lifecycleScope.launch {
            harness.state.collect { state ->
                when (state) {
                    is LlamaState.Uninitialized,
                    is LlamaState.Initializing -> {
                        enableInput(false)
                    }
                    is LlamaState.Initialized -> {
                        enableInput(false)
                        if (!hasAutoLoaded) {
                            hasAutoLoaded = true
                            loadDefaultModel()
                        }
                    }
                    is LlamaState.LoadingModel -> {
                        enableInput(false)
                    }
                    is LlamaState.ModelReady -> {
                        isModelReady = true
                        loadedModelId = harness.getSelectedModel().id
                        enableInput(true)
                        updateUIForModelType()
                    }
                    is LlamaState.ProcessingSystemPrompt,
                    is LlamaState.ProcessingUserPrompt,
                    is LlamaState.Generating -> {
                        enableInput(false)
                    }
                    is LlamaState.PrefillingImage -> {
                        isModelReady = true
                        etInput.isEnabled = true
                        btnSend.isEnabled = !isProcessingVideo
                        btnImage.isEnabled = false
                    }
                    is LlamaState.UnloadingModel -> {
                        enableInput(false)
                    }
                    is LlamaState.Error -> {
                        enableInput(false)
                    }
                }
            }
        }
    }

    private fun enableInput(enable: Boolean) {
        etInput.isEnabled = enable
        btnSend.isEnabled = enable
        if (!enable) {
            btnImage.isEnabled = false
        } else {
            btnImage.isEnabled = harness.isVisionSupported
        }
    }

    private fun shouldRedirectToTts(): Boolean {
        val model = harness.getSelectedModel()
        return model.isTts
    }

    private fun updateUIForModelType() {
        val model = harness.getSelectedModel()
        val isVision = harness.isVisionSupported

        tvTitle.setText(if (isVision) R.string.app_title else R.string.app_title_text)
        btnImage.visibility = if (isVision) View.VISIBLE else View.GONE
        btnImageSlice.visibility = if (isVision) View.VISIBLE else View.GONE
        btnImage.isEnabled = isVision

        refreshWelcomeCard(model.isTextOnly)
    }

    private fun refreshWelcomeCard(isTextOnly: Boolean) {
        val welcomeIndex = messages.indexOfFirst { it is ChatMessage.WelcomeCard }
        if (welcomeIndex >= 0) {
            messages[welcomeIndex] = ChatMessage.WelcomeCard(isTextOnly = isTextOnly)
            chatAdapter.submitList(messages.toList())
        }
    }

    private fun loadDefaultModel() {
        val availability = harness.getSelectedModelAvailability()
        val model = availability.model

        if (availability.ggufMissing || availability.supportArtifactMissing) {
            promptDownloadModels(
                ggufMissing = availability.ggufMissing,
                mmprojMissing = !model.isTextOnly && availability.supportArtifactMissing
            )
            return
        }

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                harness.loadSelectedModel()
                loadedModelId = model.id
            } catch (e: Exception) {
                Log.e(TAG, "Error loading model", e)
                harness.resetToInitialized()
                hasAutoLoaded = false
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, getString(R.string.toast_model_load_failed, e.message), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun promptDownloadModels(ggufMissing: Boolean, mmprojMissing: Boolean) {
        val message = when {
            ggufMissing && mmprojMissing ->
                getString(R.string.download_prompt_all_missing)
            mmprojMissing ->
                getString(R.string.download_prompt_mmproj_missing)
            else ->
                getString(R.string.download_prompt_incomplete)
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.download_prompt_title)
            .setMessage(message)
            .setCancelable(false)
            .setPositiveButton(R.string.go_download) { _, _ ->
                startActivity(Intent(this, ModelManagerActivity::class.java))
            }
            .setNegativeButton(R.string.later) { _, _ ->
                Toast.makeText(
                    this,
                    R.string.download_prompt_hint,
                    Toast.LENGTH_LONG
                ).show()
            }
            .show()
    }

    private val getMedia = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        uri?.let { handleSelectedMedia(it) }
    }

    private fun handleSelectedMedia(uri: Uri) {
        if (!isModelReady) {
            Toast.makeText(this, R.string.toast_load_model_first, Toast.LENGTH_SHORT).show()
            return
        }
        val mime = contentResolver.getType(uri).orEmpty()
        when {
            mime.startsWith("video/") -> handleSelectedVideo(uri)
            mime.startsWith("image/") || mime.isEmpty() -> handleSelectedImage(uri)
            else -> {
                Toast.makeText(this, getString(R.string.toast_unsupported_file, mime), Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun handleSelectedImage(uri: Uri) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val imageData = contentResolver.openInputStream(uri)?.use { input ->
                    val bitmap = BitmapFactory.decodeStream(input)
                        ?: throw RuntimeException(getString(R.string.error_decode_image))
                    val stream = ByteArrayOutputStream()
                    bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream)
                    Pair(stream.toByteArray(), bitmap)
                } ?: throw RuntimeException(getString(R.string.error_read_image))

                val (imageBytes, bitmap) = imageData

                val imageName = getFileName(uri)
                val width = bitmap.width
                val height = bitmap.height
                val sizeKb = imageBytes.size / 1024
                val imageInfo = "$width x $height ($sizeKb KB)"
                val msgId = messageIdCounter++

                withContext(Dispatchers.Main) {
                    val imageMessage = ChatMessage.UserMessage(
                        id = msgId,
                        text = "",
                        imageBitmap = bitmap,
                        imageInfo = imageInfo,
                        isPrefilling = true
                    )
                    messages.add(imageMessage)
                    chatAdapter.submitList(messages.toList()) {
                        scrollToBottom()
                    }
                }

                harness.prefillImage(imageBytes)

                isImagePrefilled = true

                withContext(Dispatchers.Main) {
                    val index = messages.indexOfFirst { it.id == msgId }
                    if (index >= 0) {
                        messages[index] = (messages[index] as ChatMessage.UserMessage).copy(
                            isPrefilling = false
                        )
                        chatAdapter.submitList(messages.toList())
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error processing image", e)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MainActivity, getString(R.string.toast_image_failed, e.message), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    /**
     * Video-understanding pipeline (iOS-equivalent
     * MBHomeViewController+CaptureVideo.processVideoFrame):
     * extract up to 64 uniformly-sampled frames off the IO dispatcher,
     * append a single chat cell with the first frame as thumbnail,
     * then hand the frames to [LlamaEngine.prefillVideoFrames] which
     * loops `prefillImage(...)` under a temporary slice=1 cap.
     *
     * Gated to MiniCPM-V-4.6 because that's where iOS enables the
     * feature and where the native nCtx bump to 8192 takes effect
     * (see prepare() in llama_jni.cpp).
     */
    private fun handleSelectedVideo(uri: Uri) {
        if (!harness.isVideoUnderstandingSupported) {
            Toast.makeText(this,
                R.string.video_only_v46,
                Toast.LENGTH_LONG).show()
            return
        }

        isProcessingVideo = true
        lifecycleScope.launch(Dispatchers.IO) {
            val msgId = messageIdCounter++
            val startNs = System.nanoTime()
            try {
                val extracted = VideoFrameExtractor.extract(applicationContext, uri)
                val info = VideoFrameExtractor.formatVideoInfo(applicationContext, extracted)
                Log.i(TAG, "Video info: $info")

                withContext(Dispatchers.Main) {
                    val videoMessage = ChatMessage.UserMessage(
                        id = msgId,
                        text = "",
                        imageBitmap = extracted.thumbnail,
                        imageInfo = info,
                        isPrefilling = true,
                        isVideo = true
                    )
                    messages.add(videoMessage)
                    chatAdapter.submitList(messages.toList()) {
                        scrollToBottom()
                    }
                }

                harness.prefillVideoFrames(extracted.frames) { current, total ->
                    withContext(Dispatchers.Main) {
                        val index = messages.indexOfFirst { it.id == msgId }
                        if (index >= 0) {
                            val cur = messages[index] as ChatMessage.UserMessage
                            messages[index] = cur.copy(
                                imageInfo = getString(R.string.video_processing_progress, info, current, total)
                            )
                            chatAdapter.submitList(messages.toList())
                        }
                    }
                }

                isImagePrefilled = true

                val elapsedMs = (System.nanoTime() - startNs) / 1_000_000
                withContext(Dispatchers.Main) {
                    isProcessingVideo = false
                    val index = messages.indexOfFirst { it.id == msgId }
                    if (index >= 0) {
                        val cur = messages[index] as ChatMessage.UserMessage
                        messages[index] = cur.copy(
                            imageInfo = getString(R.string.video_preprocessing_done, info, elapsedMs / 1000.0),
                            isPrefilling = false
                        )
                        chatAdapter.submitList(messages.toList())
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error processing video", e)
                withContext(Dispatchers.Main) {
                    isProcessingVideo = false
                    val index = messages.indexOfFirst { it.id == msgId }
                    if (index >= 0) {
                        messages.removeAt(index)
                        chatAdapter.submitList(messages.toList())
                    }
                    Toast.makeText(this@MainActivity, getString(R.string.toast_video_failed, e.message), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun getFileName(uri: Uri): String {
        val cursor = contentResolver.query(uri, null, null, null, null)
        cursor?.use {
            if (it.moveToFirst()) {
                val nameIndex = it.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                if (nameIndex >= 0) {
                    return it.getString(nameIndex)
                }
            }
        }
        return "file-${System.currentTimeMillis()}"
    }

    private fun handleUserInput() {
        val userMsg = etInput.text.toString().trim()
        if (userMsg.isEmpty()) {
            Toast.makeText(this, R.string.toast_empty_input, Toast.LENGTH_SHORT).show()
            return
        }

        etInput.clearFocus()
        (getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager)
            .hideSoftInputFromWindow(etInput.windowToken, 0)

        etInput.text = null
        enableInput(false)

        collapseAppBar()

        val msgId = messageIdCounter++
        val userMessage = ChatMessage.UserMessage(
            id = msgId,
            text = userMsg,
            imageBitmap = null,
            imageInfo = null
        )
        messages.add(userMessage)
        chatAdapter.submitList(messages.toList()) {
            scrollToBottom()
        }

        isImagePrefilled = false

        val aiMsgId = messageIdCounter++
        val aiMessage = ChatMessage.AiMessage(id = aiMsgId, text = "", isGenerating = true)
        messages.add(aiMessage)
        chatAdapter.setActiveAiMessage(aiMsgId)
        chatAdapter.submitList(messages.toList()) {
            scrollToBottom()
        }

        generationJob = lifecycleScope.launch(Dispatchers.Default) {
            val fullResponse = StringBuilder()
            val promptInput = compilePromptForHarness(userMsg)
            harness.sendChatPrompt(
                request = promptInput.request,
                predictLength = promptInput.predictLength,
            )
                .onCompletion { cause ->
                    val finalText = when {
                        cause != null -> {
                            Log.e(TAG, "Generation failed", cause)
                            getString(R.string.generation_failed, cause.message ?: cause::class.java.simpleName)
                        }
                        fullResponse.hasVisibleAssistantText() -> fullResponse.toString()
                        else -> getString(R.string.generation_empty_response)
                    }
                    if (cause == null && fullResponse.hasVisibleAssistantText()) {
                        saveCompletedHarnessTurn(
                            userMsg = userMsg,
                            assistantText = fullResponse.toString(),
                            promptInput = promptInput,
                            aiMsgId = aiMsgId,
                        )
                    }
                    withContext(Dispatchers.Main) {
                        val index = messages.indexOfFirst { it.id == aiMsgId }
                        if (index >= 0) {
                            messages[index] = (messages[index] as ChatMessage.AiMessage).copy(
                                text = finalText,
                                isGenerating = false,
                                ragMode = promptInput.compiled?.mode,
                                sources = promptInput.compiled?.sources.orEmpty(),
                                debugPrompt = promptInput.debugPrompt,
                            )
                        }
                        chatAdapter.setGeneratingDone(aiMsgId)
                        chatAdapter.clearActiveAiMessage()
                        chatAdapter.submitList(messages.toList())
                        enableInput(true)
                        scrollToBottom()
                    }
                }
                .collect { token ->
                    fullResponse.append(token)
                    withContext(Dispatchers.Main) {
                        val currentText = fullResponse.toString()
                        val index = messages.indexOfFirst { it.id == aiMsgId }
                        if (index >= 0) {
                            messages[index] = ChatMessage.AiMessage(
                                id = aiMsgId,
                                text = currentText,
                                isGenerating = true,
                                ragMode = promptInput.compiled?.mode,
                                sources = promptInput.compiled?.sources.orEmpty(),
                                debugPrompt = promptInput.debugPrompt,
                            )
                        }
                        chatAdapter.updateStreamingText(aiMsgId, currentText)
                        scrollToBottom()
                    }
                }
        }
    }

    private fun compilePromptForHarness(userMsg: String): HarnessPromptInput {
        if (currentRagMode == RagMode.OFF) {
            return HarnessPromptInput(HarnessChatRequest(userPrompt = userMsg), null)
        }
        val orchestrator = ragOrchestrator
            ?: return HarnessPromptInput(HarnessChatRequest(userPrompt = userMsg), null)
        val compiled = runCatching {
            val compiled = orchestrator.compile(
                userInput = userMsg,
                mode = currentRagMode,
                characterId = currentCharacterId,
                storyCutoff = currentStoryCutoff,
                conversationSummary = currentSession?.conversationSummary.orEmpty(),
                modelFamily = harness.getSelectedModelSpec().family,
            )
            Log.d(
                TAG,
                "Compiled ${compiled.mode} prompt: sources=${compiled.sources.size}, " +
                    "contextChars=${compiled.contextText.length}, renderedChars=${compiled.renderedPrompt.length}, " +
                    "systemChars=${compiled.rendered.splitPrompt.systemPrompt.length}, " +
                    "userChars=${compiled.rendered.splitPrompt.userPrompt.length}",
            )
            compiled
        }.getOrElse { error ->
            Log.e(TAG, "Failed to compile RAG prompt; falling back to raw user input", error)
            return HarnessPromptInput(HarnessChatRequest(userPrompt = userMsg), null)
        }
        return HarnessPromptInput(
            request = HarnessChatRequest(
                systemPrompt = compiled.rendered.splitPrompt.systemPrompt,
                userPrompt = compiled.rendered.splitPrompt.userPrompt,
            ),
            compiled = compiled,
        )
    }

    private fun StringBuilder.hasVisibleAssistantText(): Boolean =
        toString().visibleAssistantText().isNotBlank()

    private fun String.visibleAssistantText(): String {
        val start = indexOf("<think>")
        if (start < 0) return trim()
        val afterStart = substring(start + "<think>".length)
        val end = afterStart.indexOf("</think>")
        if (end < 0) return ""
        return afterStart.substring(end + "</think>".length).trim()
    }

    private fun saveCompletedHarnessTurn(
        userMsg: String,
        assistantText: String,
        promptInput: HarnessPromptInput,
        aiMsgId: Long,
    ) {
        runCatching {
            val modelId = harness.getSelectedModel().id
            val session = currentSession ?: sessionStore.create(
                characterId = currentCharacterId,
                storyCutoff = currentStoryCutoff,
                selectedModelId = modelId,
            )
            val turn = ChatTurn(
                turnId = "turn-${System.currentTimeMillis()}-$aiMsgId",
                userText = userMsg,
                assistantText = assistantText,
                ragMode = promptInput.compiled?.mode?.name ?: RagMode.OFF.name,
                sources = promptInput.compiled?.sources.orEmpty(),
                renderedPrompt = promptInput.debugPrompt,
                characterId = session.characterId,
                modelId = modelId,
            )
            val updatedSession = sessionStore.appendTurn(session, turn)
            memoryStore.observeTurn(updatedSession, turn)
            currentSession = updatedSession
        }.onFailure { error ->
            Log.e(TAG, "Failed to persist harness session turn", error)
        }
    }

    private fun showRagModeDialog() {
        val labels = arrayOf(
            getString(R.string.rag_mode_off),
            getString(R.string.rag_mode_rag),
            getString(R.string.rag_mode_character_rag),
        )
        val modes = arrayOf(RagMode.OFF, RagMode.RAG, RagMode.CHARACTER_RAG)
        val checked = modes.indexOf(currentRagMode).coerceAtLeast(0)
        AlertDialog.Builder(this)
            .setTitle(R.string.rag_mode_title)
            .setSingleChoiceItems(labels, checked) { dialog, which ->
                currentRagMode = modes[which]
                updateRagModeButton()
                Toast.makeText(
                    this,
                    getString(R.string.rag_mode_changed, labels[which]),
                    Toast.LENGTH_SHORT,
                ).show()
                dialog.dismiss()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun updateRagModeButton() {
        btnRagMode.alpha = if (currentRagMode == RagMode.OFF) 0.45f else 1.0f
        btnRagMode.contentDescription = "${getString(R.string.rag_mode)}: ${ragModeLabel(currentRagMode)}"
    }

    private fun showCharacterDialog() {
        val orchestrator = ragOrchestrator
        if (orchestrator == null) {
            Toast.makeText(this, R.string.character_list_failed, Toast.LENGTH_SHORT).show()
            return
        }
        val characters = runCatching { orchestrator.availableCharacters() }
            .onFailure { Log.e(TAG, "Failed to list characters", it) }
            .getOrDefault(emptyList())
        if (characters.isEmpty()) {
            Toast.makeText(this, R.string.character_list_failed, Toast.LENGTH_SHORT).show()
            return
        }
        val labels = characters.map { it.displayLabel() }.toTypedArray()
        val checked = characters.indexOfFirst { it.npcId == currentCharacterId }.coerceAtLeast(0)
        AlertDialog.Builder(this)
            .setTitle(R.string.character_select_title)
            .setSingleChoiceItems(labels, checked) { dialog, which ->
                switchCharacter(characters[which])
                dialog.dismiss()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun switchCharacter(character: CharacterCard) {
        if (character.npcId == currentCharacterId) return
        generationJob?.cancel()
        harness.cancelGeneration()
        currentCharacterId = character.npcId
        currentStoryCutoff = character.knowledgeScope.storyCutoff
        currentSession = null
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                if (harness.state.value is LlamaState.ModelReady) {
                    harness.clearContext()
                }
                sessionStore.clearRecentSession()
                withContext(Dispatchers.Main) {
                    clearChatUI()
                    updateCharacterButton(character)
                    Toast.makeText(
                        this@MainActivity,
                        getString(R.string.character_changed, character.identity.name),
                        Toast.LENGTH_SHORT,
                    ).show()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error switching character", e)
                withContext(Dispatchers.Main) {
                    updateCharacterButton(character)
                    Toast.makeText(
                        this@MainActivity,
                        getString(R.string.character_switch_failed, e.message),
                        Toast.LENGTH_SHORT,
                    ).show()
                }
            }
        }
    }

    private fun updateCharacterButton(character: CharacterCard? = null) {
        val label = character?.identity?.name
            ?: runCatching {
                ragOrchestrator?.availableCharacters()
                    ?.firstOrNull { it.npcId == currentCharacterId }
                    ?.identity
                    ?.name
            }.getOrNull()
            ?: currentCharacterId
        btnCharacter.contentDescription = "${getString(R.string.character_select_title)}: $label"
    }

    private fun CharacterCard.displayLabel(): String {
        return "${identity.name} (${npcId})"
    }

    private fun showSourcesDialog(sources: List<RagSource>) {
        val text = if (sources.isEmpty()) {
            getString(R.string.rag_no_sources)
        } else {
            sources.mapIndexed { index, source ->
                "${index + 1}. ${source.source}\nspan=${source.start}:${source.end}  score=${"%.4f".format(source.score)}"
            }.joinToString("\n\n")
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.rag_sources_title)
            .setMessage(text)
            .setPositiveButton(R.string.confirm, null)
            .show()
    }

    private fun showPromptDialog(prompt: String) {
        AlertDialog.Builder(this)
            .setTitle(R.string.rag_prompt_title)
            .setMessage(prompt)
            .setPositiveButton(R.string.confirm, null)
            .show()
    }

    private fun ragModeLabel(mode: RagMode): String {
        return when (mode) {
            RagMode.OFF -> getString(R.string.rag_mode_off)
            RagMode.RAG -> getString(R.string.rag_mode_rag)
            RagMode.CHARACTER_RAG -> getString(R.string.rag_mode_character_rag)
        }
    }

    private data class HarnessPromptInput(
        val request: HarnessChatRequest,
        val compiled: CompiledAndroidPrompt?,
    ) {
        val predictLength: Int
            get() = if (compiled?.mode == RagMode.CHARACTER_RAG) {
                CHARACTER_RESPONSE_TOKEN_LIMIT
            } else {
                LlamaEngine.DEFAULT_PREDICT_LENGTH
            }

        val debugPrompt: String?
            get() = compiled?.renderedPrompt
    }

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        if (ev.action == MotionEvent.ACTION_DOWN) {
            val v = currentFocus
            if (v is TextInputEditText) {
                val barRect = android.graphics.Rect()
                cardInputBar.getGlobalVisibleRect(barRect)
                if (!barRect.contains(ev.rawX.toInt(), ev.rawY.toInt())) {
                    v.clearFocus()
                    val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
                    imm.hideSoftInputFromWindow(v.windowToken, 0)
                }
            }
        }
        return super.dispatchTouchEvent(ev)
    }

    override fun onResume() {
        super.onResume()
        val currentTag = LocaleManager.currentLanguage(this).tag
        if (createdWithLocale != null && createdWithLocale != currentTag) {
            isLocaleRestart = true
            LocaleManager.recreateSeamlessly(this)
            return
        }
        // Re-check: if the model was switched to a TTS model while this
        // activity was in the background, redirect to TtsActivity.
        if (shouldRedirectToTts()) {
            startActivity(Intent(this, TtsActivity::class.java))
            finish()
            return
        }
        val selectedId = harness.getSelectedModel().id

        if (loadedModelId != null && loadedModelId != selectedId) {
            loadedModelId = null
            hasAutoLoaded = false
            reloadAfterModelSwitch()
        } else if (harness.consumeModelSwitched()) {
            loadedModelId = selectedId
            clearChatUI()
            updateUIForModelType()
        }
    }

    private fun reloadAfterModelSwitch() {
        enableInput(false)
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                if (harness.state.value is LlamaState.ModelReady) {
                    harness.unloadModel()
                }
            } catch (e: Exception) {
                Log.w(TAG, "Error unloading during model switch", e)
            }
            withContext(Dispatchers.Main) {
                clearChatUI()
                loadDefaultModel()
            }
        }
    }

    override fun onStop() {
        generationJob?.cancel()
        super.onStop()
    }

    override fun onDestroy() {
        if (isFinishing && !isLocaleRestart) {
            harness.destroy()
        }
        super.onDestroy()
    }

    companion object {
        private val TAG = MainActivity::class.java.simpleName
        private const val DEFAULT_CHARACTER_ID = "lu_jiangxian"
        private const val DEFAULT_STORY_CUTOFF = "evt-010"
        private const val CHARACTER_RESPONSE_TOKEN_LIMIT = 128
    }
}
